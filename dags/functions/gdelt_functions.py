"""
GDelt functions for Airflow DAGs.

This module contains reusable GDelt functions that are used by DAGs,
separated from the DAG definitions to avoid import issues during testing.
"""

import logging
import json
import requests
from requests.exceptions import RequestException
from datetime import datetime, timedelta
from typing import List, Dict, Any
from airflow.models import Variable

# Configure logging
logger = logging.getLogger(__name__)


def validate_gdelt_configuration() -> Dict[str, Any]:
    """
    Validate GDelt configuration from Airflow Variables.
    
    Returns:
        Dict containing validated configuration parameters
        
    Raises:
        ValueError: If required configuration is missing or invalid
    """
    try:
        # Get required variables
        keywords = Variable.get("gdelt_keywords", default_var=None, deserialize_json=True)
        logger.info(f"gdelt_keywords: {keywords}")
        if not keywords:
            raise ValueError("gdelt_keywords must contain at least one keyword")
        
        # Get API endpoint
        api_endpoint = Variable.get("gdelt_api_endpoint", default_var=None)
        if not api_endpoint:
            raise ValueError("gdelt_api_endpoint Variable is required")
        logger.info(f"gdelt_api_endpoint: {api_endpoint}")
        # Get optional parameters with defaults
        max_urls_per_run = int(Variable.get("gdelt_max_urls_per_run", default_var="100"))
        time_window_hours = int(Variable.get("gdelt_time_window_hours", default_var="1"))
        logger.info(f"gdelt_max_urls_per_run: {max_urls_per_run}")
        logger.info(f"gdelt_time_window_hours: {time_window_hours}")
        config = {
            "keywords": keywords,
            "api_endpoint": api_endpoint,
            "max_urls_per_run": max_urls_per_run,
            "time_window_hours": time_window_hours
        }
        
        logger.info(f"GDelt configuration validated: {len(keywords)} keywords, "
                   f"max_urls={max_urls_per_run}, time_window={time_window_hours}h")
        
        return config
        
    except Exception as e:
        logger.error(f"GDelt configuration validation failed: {e}")
        raise


def fetch_gdelt_urls(keywords: List[str], api_endpoint: str, 
                    time_window_hours: int, max_urls_per_run: int) -> List[Dict[str, str]]:
    """
    Fetch URLs from GDelt API based on keywords and time window.

    Returns:
        List of dictionaries with 'url' key, suitable for downstream tasks.
    """
    now = datetime.utcnow()
    start = now - timedelta(hours=time_window_hours)
    start_str = start.strftime("%Y%m%d%H%M%S")

    all_urls = []
    for keyword in keywords:
        params = {
            "query": keyword,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": max_urls_per_run,
            "sort": "DateDesc",
            "startdatetime": start_str
        }

        try:
            logger.info(f"querying gdelt: {api_endpoint} with params: {params}")
            response = requests.get(api_endpoint, params=params, timeout=10)
            logger.info(f"gdelt response: {response.status_code} {response.text}")
            if response.status_code != 200:
                raise ValueError(f"GDelt API returned status {response.status_code}: {response.text}")

            try:
                data = response.json()
                articles = data.get("articles", [])
                url_dicts = [{"url": a["url"]} for a in articles if "url" in a]
                all_urls.extend(url_dicts)

            except ValueError:
                raise ValueError("GDelt API response could not be parsed as JSON.")

        except Exception as e:
            raise ValueError(f"GDelt API request failed: {e}")

    return all_urls



def trigger_web_scraping_for_urls(urls: List[str], context=None) -> Dict[str, Any]:
    """
    Trigger web scraping DAG for each URL.
    
    Args:
        urls: List of URLs to trigger web scraping for
        context: Airflow context (optional, will get current context if not provided)
        
    Returns:
        Dict containing trigger results and statistics
    """
    try:
        from airflow.operators.trigger_dagrun import TriggerDagRunOperator
        from airflow.operators.python import get_current_context
        
        if context is None:
            context = get_current_context()
        
        triggered_count = 0
        failed_count = 0
        
        for url in urls:
            try:
                # Create unique task_id for each trigger
                task_id = f'trigger_web_scraping_{abs(hash(url)) % 10000}'
                
                # Create trigger operator for each URL
                trigger_op = TriggerDagRunOperator(
                    task_id=task_id,
                    trigger_dag_id='web_scraping_dag',
                    conf={'url': url},
                    wait_for_completion=False,
                )
                
                # Execute the trigger
                trigger_op.execute(context)
                triggered_count += 1
                logger.info(f"Triggered web scraping for URL: {url}")
                
            except Exception as e:
                logger.error(f"Failed to trigger web scraping for URL {url}: {e}")
                failed_count += 1
        
        result = {
            "urls_found": len(urls),
            "url_list": urls,
            "urls_processed": len(urls),
            "triggered_count": triggered_count,
            "failed_count": failed_count
        }
        
        logger.info(f"Web scraping trigger results: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to trigger web scraping: {e}")
        raise