"""
Database Migration DAG

This DAG handles database initialization and migration using Alembic.
It creates tables and runs migrations for the URL ingestion system.
"""

from datetime import datetime, timedelta
import logging
import sys
import os

from airflow import DAG
from airflow.decorators import task
from airflow.operators.python import get_current_context
from airflow.operators.bash import BashOperator

# Import database functions from functions module
from functions.database_functions import (
    check_database_connection,
    initialize_database,
    check_migration_status,
    create_sample_data
)


# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 7, 31),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'database_migration_dag',
    default_args=default_args,
    description='A DAG for database initialization and migration',
    schedule=None,  # Manual trigger only
    catchup=False,
    tags=['database', 'migration', 'alembic', 'initialization'],
) as dag:

    @task()
    def check_database_connection_task():
        return check_database_connection()

    @task()
    def initialize_database_task():
        return initialize_database()

    @task()
    def check_migration_status_task():
        return check_migration_status()

    # Initialize Alembic (create alembic_version table and stamp as head)
    init_alembic_task = BashOperator(
        task_id='initialize_alembic',
        bash_command="""
        cd /opt/airflow/models/alembic && \
        alembic stamp head
        """,
    )

    # Generate initial migration
    generate_migration_task = BashOperator(
        task_id='generate_initial_migration',
        bash_command="""
        cd /opt/airflow/models/alembic && \
        alembic revision --autogenerate -m "Initial migration"
        """,
    )

    # Run migrations
    run_migration_task = BashOperator(
        task_id='run_migrations',
        bash_command="""
        cd /opt/airflow/models/alembic && \
        alembic upgrade head
        """,
    )

    # DAG flow
    check_db = check_database_connection_task()
    init_db = initialize_database_task()
    check_migration = check_migration_status_task()

    # Set task dependencies
    check_db >> init_db >> init_alembic_task >> generate_migration_task >> run_migration_task >> check_migration