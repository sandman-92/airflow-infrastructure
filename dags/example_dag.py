from airflow import DAG
from airflow.decorators import task
from airflow.operators.python import get_current_context
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta

def example_function(*args, **kwargs):
    """

    :return:
    """
    return "Call this function"


default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    dag_id='example_dag',
    default_args=default_args,
    start_date=datetime.utcnow() - timedelta(days=1),
    schedule=None,
    catchup=False,
    tags=['airflow-3.0', 'example', 'fanout-fanin'],
) as dag:

    @task()
    def task_1():
        example_function()
        return "initial payload"

    @task()
    def task_2(previous):
        return ["alpha", "beta", "gamma"]

    @task()
    def task_3(item: str):
        return f"processed_{item}"

    @task()
    def task_4():
        #Context should be extracted in the task decorator
        context = get_current_context()
        ti = context["ti"]
        results = ti.xcom_pull(task_ids="task_3")
        for result in results:
            print(f"Result: {result}")
        return results

    # Trigger another DAG at the end
    trigger_called_dag = TriggerDagRunOperator(
        task_id='trigger_called_dag',
        trigger_dag_id='example_called_dag',
        wait_for_completion=False,
    )

    # DAG flow
    t1 = task_1()
    t2 = task_2(t1)
    t3_mapped = task_3.expand(item=t2)
    t4_task = task_4()

    # Set dependencies
    t3_mapped >> t4_task >> trigger_called_dag
