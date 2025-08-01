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

# Configure logging
logger = logging.getLogger(__name__)


def check_database_connection():
    """Check if database connection is working"""
    try:
        # Add models to Python path
        sys.path.insert(0, '/opt/airflow/models')
        
        from base import engine
        from sqlalchemy import text
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
            
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


def initialize_database():
    """Initialize database tables"""
    try:
        # Add models to Python path
        sys.path.insert(0, '/opt/airflow/models')
        
        from model import create_tables
        
        # Create all tables
        create_tables()
        logger.info("Database tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def check_migration_status():
    """Check current migration status"""
    try:
        # Add models to Python path
        sys.path.insert(0, '/opt/airflow/models')
        
        from base import engine
        from sqlalchemy import text
        
        # Check if alembic_version table exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'alembic_version'
                );
            """))
            
            table_exists = result.scalar()
            
            if table_exists:
                # Get current revision
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                current_revision = result.scalar()
                logger.info(f"Current migration revision: {current_revision}")
                return current_revision
            else:
                logger.info("No migration history found")
                return None
                
    except Exception as e:
        logger.error(f"Failed to check migration status: {e}")
        raise


def create_sample_data():
    """Create sample data for testing"""
    try:
        # Add models to Python path
        sys.path.insert(0, '/opt/airflow/models')
        
        from model import URLInjestion, JsonFiles
        from base import SessionLocal
        
        db = SessionLocal()
        try:
            # Check if sample data already exists
            existing_url = db.query(URLInjestion).filter(
                URLInjestion.url == "https://example.com"
            ).first()
            
            if not existing_url:
                # Create sample URL ingestion record
                sample_url = URLInjestion(
                    url="https://example.com",
                    status="Queued"
                )
                db.add(sample_url)
                db.commit()
                db.refresh(sample_url)
                
                # Create sample JSON file record
                sample_json = JsonFiles(
                    filepath="/opt/airflow/data/sample.json",
                    status="Queued",
                    url_id=sample_url.id
                )
                db.add(sample_json)
                db.commit()
                
                logger.info("Sample data created successfully")
            else:
                logger.info("Sample data already exists")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to create sample data: {e}")
        raise


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