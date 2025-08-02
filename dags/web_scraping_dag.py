"""
Web Scraping DAG

This DAG implements a web scraping workflow using the requests library and BeautifulSoup.
It includes retry logic, user agent rotation, and comprehensive error handling.
"""

from datetime import datetime, timedelta
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import sys
import os
import json
import base64
import hashlib

from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable
from airflow.operators.python import get_current_context
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

# Add models directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'models'))
from base import SessionLocal
from model import URLInjestion, JsonFiles

# Configure logging
logger = logging.getLogger(__name__)


def check_url_status(url):
    """
    Check the status of a URL in the URLInjestion table.
    
    Args:
        url (str): The URL to check
        
    Returns:
        dict: Dictionary containing:
            - 'exists' (bool): Whether the URL exists in the database
            - 'status' (str): Current status if exists, None otherwise
            - 'record' (URLInjestion): The database record if exists, None otherwise
    """
    db = SessionLocal()
    try:
        record = db.query(URLInjestion).filter(URLInjestion.url == url).first()
        if record:
            return {
                'exists': True,
                'status': record.status,
                'record': record
            }
        else:
            return {
                'exists': False,
                'status': None,
                'record': None
            }
    except Exception as e:
        logger.error(f"Error checking URL status: {e}")
        raise
    finally:
        db.close()


def create_url_record(url):
    """
    Create a new URL record with status 'Queued'.
    
    Args:
        url (str): The URL to create a record for
        
    Returns:
        URLInjestion: The created record
    """
    db = SessionLocal()
    try:
        record = URLInjestion(
            url=url,
            status="Queued",
            created_at=datetime.now()
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info(f"Created new URL record with status 'Queued' for: {url}")
        return record
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating URL record: {e}")
        raise
    finally:
        db.close()


def update_url_status(url, status):
    """
    Update the status of a URL record.
    
    Args:
        url (str): The URL to update
        status (str): The new status ('Success', 'Failed', 'Queued', 'Running')
    """
    db = SessionLocal()
    try:
        record = db.query(URLInjestion).filter(URLInjestion.url == url).first()
        if record:
            record.status = status
            record.updated_at = datetime.now()
            db.commit()
            logger.info(f"Updated URL status to '{status}' for: {url}")
        else:
            logger.warning(f"URL record not found for update: {url}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating URL status: {e}")
        raise
    finally:
        db.close()


def should_proceed_with_scraping(url, retry_url_config=False):
    """
    Determine if scraping should proceed based on URL status and configuration.
    
    Args:
        url (str): The URL to check
        retry_url_config (bool): Whether retry_url configuration is enabled
        
    Returns:
        bool: True if scraping should proceed, False otherwise
    """
    url_info = check_url_status(url)
    
    if not url_info['exists']:
        # URL doesn't exist, create record and proceed
        create_url_record(url)
        return True
    
    status = url_info['status']
    
    if status in ['Success', 'Queued'] and not retry_url_config == True:
        # Don't proceed if status is Success or Queued
        logger.info(f"URL {url} has status '{status}', skipping scraping")
        return False
    elif status == 'Failed' and retry_url_config:
        # Proceed if status is Failed but retry is configured
        logger.info(f"URL {url} has status 'Failed' but retry_url is configured, proceeding")
        return True
    elif status == 'Failed' and not retry_url_config:
        # Don't proceed if status is Failed and no retry configured
        logger.info(f"URL {url} has status 'Failed' and no retry_url configured, skipping")
        return False
    else:
        # For any other status (like 'Running'), proceed
        return True


def generate_filename_from_url(url):
    """
    Generate a base64 encoded filename from URL hash.
    
    Args:
        url (str): The URL to generate filename for
        
    Returns:
        str: Base64 encoded filename with .json extension
    """
    # Create SHA256 hash of the URL
    url_hash = hashlib.sha256(url.encode('utf-8')).digest()
    
    # Encode to base64 and decode to string, remove padding and replace unsafe chars
    filename = base64.urlsafe_b64encode(url_hash).decode('utf-8').rstrip('=')
    
    return f"{filename}.json"


def check_json_file_status(url):
    """
    Check if a JSON file record exists for the given URL.
    
    Args:
        url (str): The URL to check
        
    Returns:
        dict: Dictionary containing:
            - 'exists' (bool): Whether the file record exists
            - 'record' (JsonFiles): The database record if exists, None otherwise
            - 'filepath' (str): The filepath if exists, None otherwise
    """
    db = SessionLocal()
    try:
        # First get the URL record
        url_record = db.query(URLInjestion).filter(URLInjestion.url == url).first()
        if not url_record:
            return {'exists': False, 'record': None, 'filepath': None}
        
        # Check for JSON file record
        json_record = db.query(JsonFiles).filter(JsonFiles.url_id == url_record.id).first()
        if json_record:
            return {
                'exists': True,
                'record': json_record,
                'filepath': json_record.filepath
            }
        else:
            return {'exists': False, 'record': None, 'filepath': None}
    except Exception as e:
        logger.error(f"Error checking JSON file status: {e}")
        raise
    finally:
        db.close()


def create_json_file_record(url, filepath):
    """
    Create a new JSON file record with status 'Queued'.
    
    Args:
        url (str): The URL associated with the file
        filepath (str): The filepath of the JSON file
        
    Returns:
        JsonFiles: The created record
    """
    db = SessionLocal()
    try:
        # Get the URL record
        url_record = db.query(URLInjestion).filter(URLInjestion.url == url).first()
        if not url_record:
            raise Exception(f"URL record not found for: {url}")
        
        record = JsonFiles(
            filepath=filepath,
            status="Queued",
            url_id=url_record.id,
            created_at=datetime.now()
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info(f"Created new JSON file record with status 'Queued' for: {filepath}")
        return record
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating JSON file record: {e}")
        raise
    finally:
        db.close()


def update_json_file_status(filepath, status):
    """
    Update the status of a JSON file record.
    
    Args:
        filepath (str): The filepath to update
        status (str): The new status ('Success', 'Failed', 'Queued', 'Running')
    """
    db = SessionLocal()
    try:
        record = db.query(JsonFiles).filter(JsonFiles.filepath == filepath).first()
        if record:
            record.status = status
            record.updated_at = datetime.now()
            db.commit()
            logger.info(f"Updated JSON file status to '{status}' for: {filepath}")
        else:
            logger.warning(f"JSON file record not found for update: {filepath}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating JSON file status: {e}")
        raise
    finally:
        db.close()


def write_json_file(filepath, data):
    """
    Write JSON data to file in the request_json directory.
    
    Args:
        filepath (str): The relative filepath (filename only)
        data (dict): The data to write as JSON
        
    Returns:
        str: The full path of the written file
    """
    # Ensure the directory exists
    base_dir = "/opt/airflow/data/request_json"
    os.makedirs(base_dir, exist_ok=True)
    
    # Full path to the file
    full_path = os.path.join(base_dir, filepath)
    
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully wrote JSON file: {full_path}")
        return full_path
    except Exception as e:
        logger.error(f"Error writing JSON file {full_path}: {e}")
        raise



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
            return page
        else:
            logger.warning(f"[requests] Insufficient content scraped from URL: {url}")
            return None

    except requests.exceptions.Timeout:
        logger.warning(f"[requests] Timeout while scraping URL: {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"[requests] Failed to scrape URL: {url}, Error: {e}")
        return None
    except Exception as e:
        logger.warning(
            f"[requests] Unexpected error while scraping URL: {url}, "
            f"Error: {e}"
        )
        return None


def scrape_url_task(url, retry_url_config):
    """
    Airflow task wrapper for the scrape_with_requests function.
    
    Args:
        url: The URL to scrape
        retry_url_config: Whether to retry failed URLs
    
    This function integrates with the URLInjestion database table to track URL processing status.
    """

    # Check if we should proceed with scraping based on URL status
    if not should_proceed_with_scraping(url, retry_url_config):
        logger.info(f"Skipping scraping for URL: {url} based on database status")
        return {"status": "skipped", "url": url, "reason": "URL status check"}
    
    try:
        # Update status to Running before starting scraping
        update_url_status(url, "Running")
        
        # Perform the scraping
        result = scrape_with_requests(url)
        
        if result:
            logger.info(f"Successfully scraped content from {url}")
            logger.info(f"Title: {result.get('title', 'No title')}")
            logger.info(f"Content length: {len(result.get('text', ''))}")
            
            # Update status to Success
            update_url_status(url, "Success")
            
            # Store result in XCom for downstream tasks
            return result
        else:
            logger.error(f"Failed to scrape content from {url}")
            # Update status to Failed
            update_url_status(url, "Failed")
            raise Exception(f"Scraping failed for URL: {url}")
            
    except Exception as e:
        # Update status to Failed on any exception
        try:
            update_url_status(url, "Failed")
        except Exception as db_error:
            logger.error(f"Failed to update URL status to Failed: {db_error}")
        
        logger.error(f"Error during scraping: {e}")
        raise


def write_json(scraped_data, rewrite_file, processing_metadata):
    """
    Process the scraped content and save it as a JSON file.
    
    Args:
        scraped_data: The scraped content from the previous task
        rewrite_file: Whether to rewrite existing files
        processing_metadata: Metadata about the processing context
    
    This function:
    1. Processes scraped data from the previous task
    2. Generates a base64 encoded filename from the URL hash
    3. Checks if a JSON file record already exists in the database
    4. Creates/writes the JSON file if conditions are met
    5. Updates the database status accordingly
    """
    
    if not scraped_data:
        logger.error("No scraped content received from previous task")
        raise Exception("No content to process")
    
    # Check if scraping was skipped
    if scraped_data.get('status') == 'skipped':
        logger.info("Scraping was skipped, no JSON file to create")
        return {"status": "skipped", "reason": "scraping was skipped"}
    
    url = scraped_data['url']
    logger.info("Processing scraped content...")
    logger.info(f"Processing content from: {url}")
    logger.info(f"Title: {scraped_data.get('title', 'No title')}")
    logger.info(f"Content preview: {scraped_data['text'][:200]}...")
    
    # Generate filename from URL hash
    filename = generate_filename_from_url(url)
    logger.info(f"Generated filename: {filename}")
    logger.info(f"rewrite_file configuration: {rewrite_file}")
    
    # Check if JSON file record already exists
    file_info = check_json_file_status(url)
    
    if file_info['exists'] and not rewrite_file:
        logger.info(f"JSON file record already exists for URL {url} with status '{file_info['record'].status}' and rewrite_file is not enabled. Skipping file creation.")
        return {
            "status": "skipped", 
            "reason": "file already exists and rewrite_file not enabled",
            "existing_filepath": file_info['filepath'],
            "existing_status": file_info['record'].status
        }
    
    try:
        # Create or update the JSON file record
        if not file_info['exists']:
            # Create new record
            create_json_file_record(url, filename)
            logger.info(f"Created new JSON file record for: {filename}")
        else:
            # Update existing record status to Queued (for rewrite scenario)
            update_json_file_status(filename, "Queued")
            logger.info(f"Updated existing JSON file record status to 'Queued' for: {filename}")
        
        # Update status to Running before writing file
        update_json_file_status(filename, "Running")
        
        # Prepare JSON data to write
        json_data = {
            "url": url,
            "title": scraped_data.get('title', 'No title'),
            "text": scraped_data['text'],
            "content_length": len(scraped_data['text']),
            "scraped_at": datetime.now().isoformat(),
            "processing_metadata": processing_metadata
        }
        
        # Write the JSON file
        full_path = write_json_file(filename, json_data)
        
        # Update status to Success
        update_json_file_status(filename, "Success")
        
        logger.info(f"Successfully processed and saved JSON file: {full_path}")
        
        return {
            "status": "processed", 
            "filepath": filename,
            "full_path": full_path,
            "content_length": len(scraped_data['text']),
            "url": url
        }
        
    except Exception as e:
        # Update status to Failed on any exception
        try:
            update_json_file_status(filename, "Failed")
        except Exception as db_error:
            logger.error(f"Failed to update JSON file status to Failed: {db_error}")
        
        logger.error(f"Error during JSON file processing: {e}")
        raise Exception(f"JSON file processing failed: {e}")


def prepare_embedding_dag_params(json_result):
    """
    Prepare parameters to trigger the create_embedding_dag.
    
    Args:
        json_result: The result from the write_json task
    
    This function:
    1. Processes the result from the write_json task
    2. Retrieves URL_ID and JSON_FILE_ID from the database
    3. Reads the article text from the JSON file
    4. Returns the configuration for triggering the embedding DAG
    """
    
    if not json_result or json_result.get('status') == 'skipped':
        logger.info("JSON processing was skipped, no embedding DAG to trigger")
        return {"status": "skipped", "reason": "JSON processing was skipped"}
    
    url = json_result['url']
    filepath = json_result['filepath']
    full_path = json_result['full_path']
    
    logger.info(f"Preparing embedding DAG parameters for URL: {url}")
    logger.info(f"JSON file path: {filepath}")
    
    # Get URL_ID from database
    db = SessionLocal()
    try:
        # Get URL record
        url_record = db.query(URLInjestion).filter(URLInjestion.url == url).first()
        if not url_record:
            raise Exception(f"URL record not found for: {url}")
        
        # Get JSON file record
        json_file_record = db.query(JsonFiles).filter(JsonFiles.filepath == filepath).first()
        if not json_file_record:
            raise Exception(f"JSON file record not found for: {filepath}")
        
        url_id = url_record.id
        json_file_id = json_file_record.id
        
        logger.info(f"Found URL_ID: {url_id}, JSON_FILE_ID: {json_file_id}")
        
        # Read the article text from the JSON file
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                article_text = json_data.get('text', '')
                
            if not article_text:
                raise Exception("No article text found in JSON file")
                
            logger.info(f"Article text length: {len(article_text)} characters")
            
            # Prepare configuration for the embedding DAG
            embedding_dag_config = {
                'URL_ID': url_id,
                'JSON_FILE_ID': json_file_id,
                'text': article_text,
                'model': 'text-embedding-3-small',  # Default model
                'QdrantCollection': 'FullTextEmbedding'  # Default collection
            }
            
            logger.info("Successfully prepared embedding DAG parameters")
            return embedding_dag_config
            
        except Exception as file_error:
            logger.error(f"Error reading JSON file {full_path}: {file_error}")
            raise Exception(f"Failed to read article text: {file_error}")
            
    except Exception as e:
        logger.error(f"Error preparing embedding DAG parameters: {e}")
        raise
    finally:
        db.close()




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
    'web_scraping_dag',
    default_args=default_args,
    description='A DAG for web scraping using requests and BeautifulSoup',
    catchup=False,
    tags=['web-scraping', 'requests', 'beautifulsoup'],
) as dag:

    @task()
    def scrape_url():
        context = get_current_context()
        dag_run = context.get("dag_run")

        if not dag_run or not dag_run.conf:
            raise ValueError("No configuration provided in dag_run.conf")

        conf = dag_run.conf
        url = conf.get("url")['url']
        retry_url_config = conf.get("retry_url", False)

        if not url:
            raise ValueError("Missing 'url' in dag_run.conf")

        logger.info(f"[scrape_url] Extracted URL: {url}")
        logger.info(f"[scrape_url] Retry flag: {retry_url_config}")
        return scrape_url_task(url, retry_url_config)


    @task()
    def process_content(scraped_data: dict):
        logger.info(f"[process_content] Received scraped_data keys: {list(scraped_data.keys())}")
        context = get_current_context()

        dag_run = context.get('dag_run')
        rewrite_file = False
        if dag_run and dag_run.conf and 'rewrite_file' in dag_run.conf:
            rewrite_file = dag_run.conf['rewrite_file']

        logger.info(f"[process_content] rewrite_file: {rewrite_file}")

        processing_metadata = {
            "dag_run_id": dag_run.run_id if dag_run else None,
            "task_instance_id": context.get('task_instance').task_id if context.get('task_instance') else None,
            "execution_date": context.get('execution_date').isoformat() if context.get('execution_date') else None
        }

        logger.info(f"[process_content] metadata: {processing_metadata}")
        return write_json(scraped_data, rewrite_file, processing_metadata)

    @task()
    def prepare_embedding_params(json_result: dict):
        logger.info(f"[prepare_embedding_params] Input JSON result keys: {list(json_result.keys())}")
        return prepare_embedding_dag_params(json_result)

    def should_trigger_embedding(**context):
        ti = context['ti']
        logger.info(f"[should_trigger_embedding] Triggering with context: {context}")

    @task()
    def trigger_embedding_dag(embedding_params: dict):
        logger.info(f"[trigger_embedding_dag] Triggering with config: {embedding_params}")

        from airflow.operators.trigger_dagrun import TriggerDagRunOperator

        trigger_op = TriggerDagRunOperator(
            task_id='trigger_create_embedding_dag_internal',
            trigger_dag_id='create_embedding',
            conf=embedding_params,
            wait_for_completion=False,
        )

        return trigger_op.execute(get_current_context())

    # DAG flow with explicit data passing
    scrape_task = scrape_url()
    write_task = process_content(scrape_task)
    prepare_task = prepare_embedding_params(write_task)
    trigger_task = trigger_embedding_dag(prepare_task)

    # Set task dependencies
    scrape_task >> write_task >> prepare_task >> trigger_task
