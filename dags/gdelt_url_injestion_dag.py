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
    description='Fetch URLs from GDelt and trigger a scraping DAG for each',
    start_date=datetime.utcnow() - timedelta(days=1),
    schedule='*/10 * * * *',
    catchup=False,
    tags=['gdelt', 'url-injestion'],
) as dag:

    @task()
    def validate_configuration_task():
        return validate_gdelt_configuration()

    @task()
    def fetch_and_write_urls(config: dict) -> list[dict]:
        urls = fetch_gdelt_urls(
            keywords=config["keywords"],
            api_endpoint=config["api_endpoint"],
            time_window_hours=config["time_window_hours"],
            max_urls_per_run=config["max_urls_per_run"]
        )
        os.makedirs(DATA_DIR, exist_ok=True)
        file_path = os.path.join(
            DATA_DIR, f"gdelt_urls_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.json"
        )
        with open(file_path, "w") as f:
            json.dump(urls, f, indent=4)
        return urls


    # Trigger web_scraping_dag for each config
    trigger_scrapers = TriggerDagRunOperator.partial(
        task_id="trigger_scraping_dags",
        trigger_dag_id="web_scraping_dag",
        wait_for_completion=False,
        reset_dag_run=False,
    ).expand(conf=)

