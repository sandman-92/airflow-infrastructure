"""
Database Migration DAG

This DAG handles database initialization and migration using Alembic.
It creates tables and runs migrations for the URL ingestion system.
"""

"""
Database Migration DAG

This DAG handles database initialization and migration using Alembic.
It creates tables and runs migrations for the URL ingestion system.
"""

import logging
import os
import sys
from datetime import datetime, timedelta

# Ensure model path is included
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from airflow import DAG
from airflow.decorators import task
from airflow.operators.bash import BashOperator
from models.base import Base, get_current_engine
from sqlalchemy import text

logger = logging.getLogger(__name__)


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


def check_database_connection():
    """Check if database connection is working"""
    try:


        # Test connection with fresh engine based on current environment
        engine = get_current_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return {"success": True}

    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return {"success": False, "error": str(e)}


def initialize_database():
    """Initialize database tables"""
    try:
        # Add models to Python path

        # Create all tables using current engine
        engine = get_current_engine()
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return {"success": True}

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return {"success": False, "error": str(e)}


def check_migration_status():
    """Check current migration status"""
    try:
        # Add models to Python path

        engine = get_current_engine()
        with engine.connect() as conn:
            # Use SQLite-compatible query for checking table existence
            result = conn.execute(text("""
                                       SELECT name
                                       FROM sqlite_master
                                       WHERE type = 'table'
                                         AND name = 'alembic_version'
                                       UNION ALL
                                       SELECT table_name
                                       FROM information_schema.tables
                                       WHERE table_name = 'alembic_version'
                                       """))

            table_exists = result.fetchone() is not None

            if table_exists:
                # Get current revision
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                current_revision = result.scalar()
                logger.info(f"Current migration revision: {current_revision}")
                return {"status": "migrated", "revision": current_revision}
            else:
                logger.info("No migration history found")
                return {"status": "no_migration", "revision": None}

    except Exception as e:
        logger.error(f"Failed to check migration status: {e}")
        return {"status": "error", "error": str(e)}


