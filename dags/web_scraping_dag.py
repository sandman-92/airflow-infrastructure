import hashlib
import json
import logging
import os
import pprint
import sys
from datetime import datetime, timedelta
from typing import Any

import requests
from airflow import DAG
from airflow.decorators import task
from airflow.operators.python import get_current_context
from airflow.sdk import Variable
from airflow.exceptions import AirflowSkipException
from bs4 import BeautifulSoup
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance
from qdrant_client.http.models import PointStruct, VectorParams
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from models.base import SessionLocal
from models.model import URL, Embedding
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

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

        conf['collection'] = Variable.get("collection", "test_urls")

        logger.info("web scraping dag called with conf")
        logger.info("conf:\n%s", pprint.pformat(conf, indent=2))

        logger.info("Running Dag with config:\n%s", pprint.pformat(conf, indent=2))

        return conf


    @task()
    def check_should_scrape(config):
        """
        Check if we should scrape this URL.
        If it doesn't exist in the DB, insert it and mark it for scraping.
        """
        logger.info("Running check_should_scrape task with config \n%s", pprint.pformat(config, indent=2))
        session = SessionLocal()
        try:
            url_obj = session.query(URL).filter(URL.url == config["url"]).first()

            if url_obj:
                # Already in DB
                config["url_id"] = url_obj.id
                config["TriggerScraper"] = url_obj.json_file_path is None
            else:
                # Not in DB — insert
                new_url = URL(url=config["url"])
                session.add(new_url)
                session.commit()
                session.refresh(new_url)

                config["url_id"] = new_url.id
                config["TriggerScraper"] = True

        except Exception as e:
            logger.error(f"check_should_scrape error: {e}")
            raise
        finally:
            session.close()

        logger.info("Exiting check_should_scrape with config \n%s", pprint.pformat(config, indent=2))
        return config


    @task()
    def scrape_url(config):

        logger.info("Running scrape_url task with config \n%s", pprint.pformat(config, indent=2))

        if not config.get("TriggerScraper"):
            return config

        logger.info(f"Scraping URL: {config['url']}")
        page, status = scrape_with_requests(config["url"])

        if status == "Failed":
            config["TriggerJson"] = False
            config["TriggerEmbedding"] = False
            raise UserWarning("Scraping failed.")

        # Save scraped data to config
        config["scraped_text"] = page["text"]
        config["scraped_title"] = page.get("title")

        return config

    @task()
    def should_write_json(config: dict, base_path: str = "/opt/airflow/data/request_json", session=None) -> dict:
        """
        Determines if JSON should be written for a URL. Computes a hash-based filepath and updates DB if needed.

        Args:
            config: Dictionary with at least "url" key.
            base_path: Where JSON files are written (default is Airflow container data folder).
            session: Optional SQLAlchemy session (for testability).

        Returns:
            config dict with updated keys:
                - "json_file_path"
                - "TriggerJson": True/False
        """
        logger.info("Running should_write_json task with config \n%s", pprint.pformat(config, indent=2))


        session = session or SessionLocal()
        url = config["url"]

        try:
            url_obj = session.query(URL).filter(URL.url == url).first()
            if not url_obj:
                raise ValueError(f"URL not found in database: {url}")

            # If already has path, assume written
            if url_obj.json_file_path:
                config["json_file_path"] = url_obj.json_file_path
                config["TriggerJson"] = False
                return config

            # Compute path
            hashed_filename = hash_url_for_filename(url)
            json_path = os.path.join(base_path, f"{hashed_filename}")

            # Update DB
            url_obj.json_file_path = json_path
            session.commit()

            config["json_file_path"] = json_path
            config["TriggerJson"] = True
            return config

        finally:
            session.close()

    @task()
    def write_json(config):

        logger.info("Running write_json task with config \n%s", pprint.pformat(config, indent=2))

        if not config.get("TriggerJson"):
            return config

        filepath = config['json_file_path']
        with open(filepath, "w") as f:
            json.dump({
                "url": config["url"],
                "title": config.get("scraped_title"),
                "text": config["scraped_text"],
            }, f)

        session = SessionLocal()
        try:
            url_obj = session.query(URL).get(config["url_id"])
            url_obj.json_file_path = filepath
            session.commit()
        finally:
            session.close()

        config["json_file_path"] = filepath
        return config


    @task()
    def should_trigger_embeddings(config: dict, session=None) -> dict:
        """
        Checks whether to trigger embedding for the URL.
        If not already embedded, creates a placeholder entry to avoid race conditions.

        Returns:
            Updated config with:
                - "url_id"
                - "collection"
                - "TriggerEmbedding"
        """
        logger.info("Running should_trigger_embeddings task with config \n%s", pprint.pformat(config, indent=2))

        session = session or SessionLocal()
        url = config["url"]
        collection = config.get("collection", "full_text_embedding")

        if not collection:
            raise ValueError("Missing 'collection' in config — required to insert Embedding row.")

        try:
            url_obj = session.query(URL).filter(URL.url == url).first()
            if not url_obj:
                raise ValueError(f"URL not found in database: {url}")

            config["url_id"] = url_obj.id
            config["collection"] = collection  # propagate for later tasks

            existing = session.query(Embedding).filter(Embedding.url_id == url_obj.id).first()
            if existing:
                config["TriggerEmbedding"] = False
                return config

            # Insert placeholder with collection
            placeholder = Embedding(
                url_id=url_obj.id,
                collection=collection,
                qdrant_index=None,
            )
            session.add(placeholder)
            session.commit()

            config["TriggerEmbedding"] = True
            return config

        except Exception as e:
            session.rollback()
            logger.error(f"Error in should_trigger_embeddings: {e}")
            config["TriggerEmbedding"] = False
            raise

        finally:
            session.close()


    @task()
    def fetch_embedding_save_qdrant(config):
        """

        Args:
            config:

        Returns:

        """

        logger.info("Running getting_embedding task with config \n%s", pprint.pformat(config, indent=2))

        collection = config.get('collection', 'full_text_embedding')
        model_name = config.get('model_name', 'text-embedding-3-small')


        if not config.get("TriggerEmbedding", False):
            logger.info("TriggerEmbedding is False. Skipping embedding generation.")
            return config

        if "scraped_text" not in config or not config["scraped_text"]:
            raise ValueError("Missing 'scraped_text' in config. Cannot generate embedding.")

        # fetch embedding
        try:

            embedding_vector = generate_embedding(
                content=config["scraped_text"],
                model=model_name,
                client=OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            )
        except Exception as embed_err:
            logger.error(f"Embedding generation failed: {embed_err}")
            config["embedding_created"] = False
            raise

        # Save to Qdrant
        try:
            qdrant_host = os.getenv("QDRANT_HOST", "qdrant")
            qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
            client = QdrantClient(host=qdrant_host, port=qdrant_port)

            # Ensure collection exists
            if not client.collection_exists(collection):
                logger.info(f"Collection '{collection}' does not exist. Creating it...")
                client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(
                        size=len(embedding_vector),  # must match your embedding size
                        distance=Distance.COSINE  # or EUCLID/ DOT depending on use case
                    )
                )

            point = PointStruct(
                id=config["url_id"],  # Ensure this is a unique and consistent ID
                vector=embedding_vector,
                payload={
                    "url": config["url"],
                    "title": config.get("scraped_title"),
                    "collection": collection,
                }
            )

            client.upsert(collection_name=collection, points=[point])
            logger.info(f"Successfully saved embedding for URL: {config['url']}")
            config["embedding_created"] = True
        except Exception as qdrant_err:
            logger.error(f"Failed to save to Qdrant: {qdrant_err}")
            config["embedding_created"] = False
            raise

        #update the db
        try:
            session = SessionLocal()
            embedding_entry = Embedding(
                url_id=config["url_id"],
                collection=collection,
                qdrant_index=str(config["url_id"])  # If you're using `url_id` as Qdrant index
            )
            session.add(embedding_entry)
            session.commit()
            session.refresh(embedding_entry)
        except Exception as e:
            logger.error(f"Embedding or DB update failed: {str(e)}")
            config["embedding_created"] = False
            raise
        finally:
            session.close()

        return config

    conf = validate_inputs()
    scrape_check = check_should_scrape(conf)
    scraped_output = scrape_url(scrape_check)
    json_trigger = should_write_json(scraped_output)
    written_json_conf = write_json(json_trigger)
    should_trigger_embedding_conf = should_trigger_embeddings(written_json_conf)
    fetched_embedding_conf = fetch_embedding_save_qdrant(should_trigger_embedding_conf)


# Functions
def get_or_create_url_entry(config, session: SessionLocal = None) -> dict:
    """
    Ensures URL exists in the `urls` table.
    """
    session = session or SessionLocal()
    try:
        url_obj = session.query(URL).filter(URL.url == config["url"]).first()
        if not url_obj:
            url_obj = URL(url=config["url"])
            session.add(url_obj)
            session.commit()
            session.refresh(url_obj)

        config["url_id"] = url_obj.id
        config["json_file_path"] = url_obj.json_file_path  # might be None

    finally:
        session.close()

    return config









def update_row( model, filters: dict, updates: dict, session:SessionLocal = None) -> bool:
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
    session = session or SessionLocal()
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


def hash_url_for_filename(url: str) -> str:
    # Generate SHA-256 hash and clean up to start with alphanumeric
    raw_hash = hashlib.sha256(url.encode()).hexdigest()
    filename = f"fn_{raw_hash}.json"
    return filename

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
            "User-Agent": "MyResearchBot/1.0 (+mailto:asw@woodthilsted.com)",
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
            raise AirflowSkipException(f"Insufficient content scraped from URL: {url}")


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


def generate_embedding(content: str, client: OpenAI = None, model: str = "text-embedding-3-small"):
    """
    Generate embedding using OpenAI API with test mode support.

    Args:
        content (str): The text content to embed
        client (OpenAI): The OpenAI client instance
        model (str): The embedding model to use

    Returns:
        list: The embedding vector as a list of floats
    """

    logger.info(f"Generating embedding for content")
    logger.info(f"using model {model}")
    client = client or OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    )

    try:
        response = client.embeddings.create(
            model=model,
            input=content,
        )
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise
    return response.data[0].embedding