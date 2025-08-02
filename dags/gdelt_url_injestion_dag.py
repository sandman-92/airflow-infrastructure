from airflow import DAG
from airflow.decorators import task
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta
import json
import os

from functions.gdelt_functions import (
    validate_gdelt_configuration,
    fetch_gdelt_urls
)

default_args = {
    'owner': 'airflow',
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

DATA_DIR = "/opt/airflow/data/url_batches"

with DAG(
    dag_id='gdelt_url_injestion_dag',
    default_args=default_args,
    start_date=datetime.utcnow() - timedelta(days=1),
    schedule='*/10 * * * *',
    catchup=False,
    tags=['airflow-3.0', 'gdelt', 'fanout'],
) as dag:

    @task()
    def validate_config():
        return validate_gdelt_configuration()

    @task()
    def fetch_urls(config: dict) -> list[dict]:
        urls = fetch_gdelt_urls(
            keywords=config["keywords"],
            api_endpoint=config["api_endpoint"],
            time_window_hours=config["time_window_hours"],
            max_urls_per_run=config["max_urls_per_run"]
        )
        # Return list of {"url": ...} dicts
        return [{"url": u} for u in urls]

    # Fan-out trigger for each URL
    trigger_scrapers = TriggerDagRunOperator.partial(
        task_id="trigger_web_scrapers",
        trigger_dag_id="web_scraping_dag",
        wait_for_completion=False,
        reset_dag_run=False,
    ).expand(conf=fetch_urls(validate_config()))

