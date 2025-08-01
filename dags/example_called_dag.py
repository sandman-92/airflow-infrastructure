from airflow import DAG
from airflow.decorators import task
from datetime import datetime, timedelta

default_args = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="example_called_dag",
    start_date=datetime.utcnow() - timedelta(days=1),
    schedule=None,
    catchup=False,
    tags=["called"],
) as dag:

    @task()
    def greet():
        print("Hello from the called DAG!")

    greet()
