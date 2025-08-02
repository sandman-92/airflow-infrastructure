from datetime import datetime, timedelta
import logging
import json
import sys
import os
from typing import Dict, Any, Optional
import uuid
import random

from airflow import DAG
from airflow.operators.python import PythonOperator, get_current_context
from airflow.decorators import task
from airflow.models import Variable

# Import embedding functions from functions module
from functions.embedding_functions import (
    check_embedding_exists,
    generate_embedding,
    generate_text_embedding,
    store_embedding_in_qdrant
)

# Configure logging
logger = logging.getLogger(__name__)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 8, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'create_embedding',
    default_args=default_args,
    description='Create text embeddings with database checking and store in Qdrant vector database',
    schedule=None,  # Triggered manually or by other DAGs
    catchup=False,
    tags=['embedding', 'qdrant', 'nlp', 'database'],
) as dag:

    @task()
    def check_embedding_exists_task():
        context = get_current_context()
        dag_run = context['dag_run']
        conf = dag_run.conf or {}

        logger.info(f"running embedding on {dag_run.conf}")
        url_id = conf.get('URL_ID')
        json_file_id = conf.get('JSON_FILE_ID')

        return check_embedding_exists(url_id, json_file_id)

    def generate_text_embedding_callable(**context):
        ti = context['ti']
        dag_run = context['dag_run']
        conf = dag_run.conf or {}

        check_result = ti.xcom_pull(task_ids='check_embedding_exists_task')
        text = conf.get('text')
        model = conf.get('model', "text-embedding-3-small")

        return generate_text_embedding(check_result, text, model)

    generate_task = PythonOperator(
        task_id='generate_text_embedding_task',
        python_callable=generate_text_embedding_callable,
        pool_slots=1,
        pool='embedding',
    )

    @task()
    def store_embedding_in_qdrant_task():
        context = get_current_context()
        ti = context['ti']
        dag_run = context['dag_run']
        conf = dag_run.conf or {}

        url_id = conf.get('URL_ID')
        json_file_id = conf.get('JSON_FILE_ID')
        qdrant_collection = conf.get('QdrantCollection', 'FullTextEmbedding')

        embedding_result = ti.xcom_pull(task_ids='generate_text_embedding_task')
        logger.info(f"Embedding result: {embedding_result}")

        return store_embedding_in_qdrant(url_id, json_file_id, qdrant_collection, embedding_result)

    # DAG flow
    check_task = check_embedding_exists_task()
    store_task = store_embedding_in_qdrant_task()

    check_task >> generate_task >> store_task
