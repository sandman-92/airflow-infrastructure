from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow import DAG
from airflow.decorators import task
from datetime import datetime, timedelta
import json
import logging
import os
import pprint

DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "data/test_urls")
logger = logging.getLogger(__name__)

default_args = {
    'owner': 'airflow',
    'retries': 0,
}

with DAG(
    dag_id='injest_test_urls',
    default_args=default_args,
    start_date=datetime.utcnow() - timedelta(days=1),
    catchup=False,
) as dag:

    @task()
    def load_json_files():
        urls = []
        list_files = os.listdir(DATA_DIR)

        for file in list_files:
            logger.info("reading file %s", file)
            with open(os.path.join(DATA_DIR, file), "r") as f:
                urls.extend(json.load(f))

        logger.info("triggering urls \n%s", pprint.pformat(urls, indent=2))

        logger.info("count urls: %s", len(urls))
        # Add 'collection' key
        return [{**url_dict, 'collection': 'test_urls', "url": url_dict['uri']} for url_dict in urls]

    # This is dynamic task mapping using the TaskFlow API
    TriggerDagRunOperator.partial(
        task_id="trigger_web_scrapers",
        trigger_dag_id="web_scraping_dag",
        wait_for_completion=False,
        reset_dag_run=False,
        retry_delay=timedelta(minutes=1),
    ).expand(conf=load_json_files())
