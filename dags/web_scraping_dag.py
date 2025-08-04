from airflow import DAG
from airflow.decorators import task
from airflow.sdk import Variable
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from airflow.operators.python import get_current_context
from datetime import datetime, timedelta
from typing import Any
import logging
import pprint

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from models.base import SessionLocal
from models.model import URLInjestion, TaskStatus, GdeltKeywords, URLKeyWordTable, JsonFiles, \
    FullArticleTextEmbedding
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import IntegrityError
logger = logging.getLogger(__name__)
# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 7, 31),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    "web_scraping_dag",
    default_args=default_args,
    description="a workflow to scrape URLS and produce embeddings",
    tags=["web-scraping", "embeddings"],
) as dag:

    @task()
    def validate_inputs():
        context = get_current_context()
        dag_run = context["dag_run"]
        conf = dag_run.conf or {}

        conf["TriggerScraper"] = True
        conf["OverrideTriggerScraper"] = Variable.get("scrape_url_override", False)

        conf["TriggerURLMetaData"] = True
        conf["OverrideTriggerURLMetaData"] = Variable.get("url_meta_data_override", False)

        conf["TriggerJson"] = True
        conf["OverrideTriggerJson"] = Variable.get("json_write_override", False)

        conf["TriggerEmbedding"] = True
        conf["OverrideTriggerEmbedding"] = Variable.get("trigger_embeddings_override", False)

        logger.info("web scraping dag called with conf")
        logger.info("conf:\n%s", pprint.pformat(conf, indent=2))

        return conf

    @task()
    def check_to_run_scraping(config):
        return check_and_update_database(config, task_to_run="scraping")

    @task()
    def scrape_url(config):
        if config["TriggerScraper"] or config["OverrideTriggerScraper"]:
            try:
                page, status = scrape_with_requests(config["url"])
                logger.info(f"Scraped page title: {page.get('title')}")
            except Exception as e:
                logger.warning(f"Scraping failed: {e}")
                status = "Failed"

            if status == "Failed":

                config['TriggerJson'] = False
                config['TriggerEmbedding'] = False
                raise UserWarning('Failed, dont run downstream tasks')
        return config

    @task()
    def check_to_write_json(config):
        """

        :return:
        """
        return check_and_update_database(config, task_to_run='writejson')

    @task()
    def write_json(config):
        """

        :return:
        """
        logger.info("WRITE JSON IS RUNNING")
        if config["TriggerJson"] or config["OverrideTriggerJson"]:
            logger.info("WRITE JSON IS RUNNING")
        #     try:
        #         page, status = scrape_with_requests(config["url"])
        #         logger.info(f"Scraped page title: {page.get('title')}")
        #     except Exception as e:
        #         logger.warning(f"Scraping failed: {e}")
        # return config

    # ✅ Define the task chain without calling them at parse time
    validate_inputs_output = validate_inputs()
    check_to_run_scraping_output = check_to_run_scraping(validate_inputs_output)
    scrape_url(check_to_run_scraping_output)


    # @task()
    # def check_to_update_metadata(config):
    #     """
    #     Task will check the  table to see if the url exists and update the db.
    #     if URL exists will set TriggerScraper = True
    #     :param config:
    #     :return:
    #     """
    #     return_conf = check_and_update_database(config, task_to_run='metadata')
    #     return return_conf
    #
    # @task()
    # def update_metadata(config):
    #     """
    #
    #     :param config:
    #     :return:
    #     """
    #     try:
    #         update_metadata(config)
    #     except Exception:
    #         pass
    #
    #

    #
    # @task()
    # def check_to_run_embedding(config):
    #     """
    #
    #     :return:
    #     """
    #     result = check_and_update_database(config, task_to_run='embedding')
    #     return result
    #
    # @task()
    # def run_embedding():
    #     """
    #
    #     :return:
    #     """
    #     pass






def check_and_update_database(config: dict, task_to_run: str, session: SessionLocal = None, set_status: str = "Running"):
    logger.info(f"Checking {task_to_run} table for previous record")

    task_to_run_lookup = {
        "scraping": (URLInjestion, "TriggerScraper", URLInjestion.url, "url"),
        "writejson": (JsonFiles, "TriggerJson", JsonFiles.filepath, "filepath"),
        "embedding": (FullArticleTextEmbedding, "TriggerEmbedding", FullArticleTextEmbedding.url_id, "url_id"),
    }

    table, trigger_variable, table_column, config_key = task_to_run_lookup[task_to_run]

    session = session or SessionLocal()

    try:
        # Ensure URL ID exists for writejson/embedding tasks
        if task_to_run in {"writejson", "embedding"}:
            if "url_id" not in config:
                url_str = config["url"]
                url_obj = session.query(URLInjestion).filter(URLInjestion.url == url_str).first()
                if not url_obj:
                    raise ValueError(f"No URLInjestion found for: {url_str}")
                config["url_id"] = url_obj.id

        lookup_item = config[config_key]
        existing = session.query(table).filter(table_column == lookup_item).first()

        status_id = get_or_create_injestion_status(status_name=set_status, session=session)
        kwargs = {
            config_key: lookup_item,
            "status_id": status_id
        }

        if task_to_run in {"writejson", "embedding"}:
            kwargs["url_id"] = config["url_id"]

        if task_to_run == "embedding":
            # Resolve json_file_id using filepath from config
            if "filepath" not in config:
                raise ValueError("Missing 'filepath' in config for embedding task")
            json_file = session.query(JsonFiles).filter_by(filepath=config["filepath"]).first()
            if not json_file:
                raise ValueError(f"No JsonFiles entry found for filepath: {config['filepath']}")
            kwargs["json_file_id"] = json_file.id

        if existing:
            logger.info(f"{lookup_item} exists in {task_to_run}, setting {trigger_variable} to False")
            config[trigger_variable] = False
        else:
            logger.info(f"{lookup_item} does NOT exist in {task_to_run}, setting {trigger_variable} to True")
            new_entry = table(**kwargs)
            session.add(new_entry)
            session.commit()
            config[trigger_variable] = True

    except Exception as exc:
        logger.warning(f"Exception Raised: {exc}")
        config[trigger_variable] = False
        raise
    finally:
        session.close()

    return config



def get_or_create_injestion_status(status_name: str, session: SessionLocal = None) -> int:
    session = session or SessionLocal()
    try:
        # First try to get it
        status = session.query(TaskStatus).filter_by(name=status_name).first()
        if status:
            return status.id

        # Try to create it
        new_status = TaskStatus(name=status_name)
        session.add(new_status)
        session.commit()
        session.refresh(new_status)
        return new_status.id

    except IntegrityError:
        session.rollback()
        # Someone else inserted it first, get it again
        status = session.query(TaskStatus).filter_by(name=status_name).first()
        if status:
            return status.id
        raise RuntimeError(f"Race condition: status '{status_name}' not found after IntegrityError")

    except Exception as e:
        session.rollback()
        raise RuntimeError(f"Failed to get or create status '{status_name}': {e}")

    finally:
        session.close()





def update_row( model, filters: dict, updates: dict) -> bool:
    """
    Updates a row in the given SQLAlchemy model/table.

    Args:
        session: SQLAlchemy session.
        model: The table model class (e.g., URLInjestion).
        filters: Dictionary of conditions to locate the row (e.g., {"url": "https://..."})
        updates: Dictionary of values to update (e.g., {"url_status_id": 2})

    Returns:
        True if a row was updated, False if no matching row was found.
    """
    session = SessionLocal()
    try:
        row = session.query(model).filter_by(**filters).first()
        if not row:
            return False

        for key, value in updates.items():
            setattr(row, key, value)

        session.commit()
        return True

    except SQLAlchemyError as e:
        session.rollback()
        raise RuntimeError(f"Failed to update {model.__tablename__}: {e}")
    finally:
        session.close()


def scrape_with_requests(url):
    """
    Attempts to scrape a webpage using the requests library and BeautifulSoup.
    This is the most efficient scraping method but may not work for JavaScript-
    heavy sites.

    The function implements:
    - Retry logic with exponential backoff
    - Realistic user agent rotation
    - Content cleaning and validation
    - Error handling and logging

    Args:
        url (str): The URL to scrape.

    Returns:
        dict or None: A dictionary containing:
            - 'title' (str): The page title
            - 'text' (str): The cleaned page content
            - 'url' (str): The original URL
        Returns None if scraping fails or content is insufficient.

    Note:
        This method is optimized for speed and efficiency but may not work
        for sites that require JavaScript execution.
    """

    try:
        # Configure session with timeouts and retries
        session = requests.Session()
        retry = Retry(
            total=3,  # Number of retries
            backoff_factor=0.5,  # Wait 0.5, 1, 2 seconds between retries
            status_forcelist=[500, 502, 503, 504],  # Retry on these codes
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set headers with a realistic user agent
        accept = (
            "text/html,application/xhtml+xml,application"
            "/xml;q=0.9,image/webp,*/*;q=0.8"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # Make request with timeouts
        response = session.get(
            url,
            headers=headers,
            timeout=(10, 30),
            # (connect timeout, read timeout)
        )
        response.raise_for_status()

        # Use BeautifulSoup to parse the HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title = soup.title.string if soup.title else None

        # Remove script, style, and other non-content elements
        for element in soup(
            ["script", "style", "nav", "footer", "header", "aside", "iframe"]
        ):
            element.decompose()

        # Get text content
        text = soup.get_text()

        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        if len(text) > 1000:  # Only return if we have substantial content
            page = {"title": title, "text": text, "url": url}
            logger.info(f"[requests] Successfully scraped URL: {url}")
            return page, 'Success'
        else:
            logger.warning(f"[requests] Insufficient content scraped from URL: {url}")
            return {}, "Failed"

    except requests.exceptions.Timeout:
        logger.warning(f"[requests] Timeout while scraping URL: {url}")
        return {}, "Failed"
    except requests.exceptions.RequestException as e:
        logger.warning(f"[requests] Failed to scrape URL: {url}, Error: {e}")
        return {}, "Failed"
    except Exception as e:
        logger.warning(
            f"[requests] Unexpected error while scraping URL: {url}, "
            f"Error: {e}"
        )
        return {}, "Failed"
