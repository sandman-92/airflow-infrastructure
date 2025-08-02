"""
Database functions for Airflow DAGs.

This module contains reusable database functions that are used by DAGs,
separated from the DAG definitions to avoid import issues during testing.
"""

import logging
import sys
import os

# Configure logging
logger = logging.getLogger(__name__)


def check_database_connection():
    """Check if database connection is working"""
    try:
        # Add models to Python path
        sys.path.insert(0, '/opt/airflow/models')
        
        from base import get_current_engine
        from sqlalchemy import text
        
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
        sys.path.insert(0, '/opt/airflow/models')
        
        from base import get_current_engine, Base
        
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
        sys.path.insert(0, '/opt/airflow/models')
        
        from base import get_current_engine
        from sqlalchemy import text
        
        # Check if alembic_version table exists with fresh engine
        engine = get_current_engine()
        with engine.connect() as conn:
            # Use SQLite-compatible query for checking table existence
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='alembic_version'
                UNION ALL
                SELECT table_name FROM information_schema.tables 
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


def create_sample_data():
    """Create sample data for testing"""
    try:
        # Add models to Python path
        sys.path.insert(0, '/opt/airflow/models')
        
        from model import URLInjestion, JsonFiles
        from base import get_current_session
        
        # Get fresh session based on current environment
        db = get_current_session()
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
                return {"success": True}
            else:
                logger.info("Sample data already exists")
                return {"success": True, "message": "Sample data already exists"}
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to create sample data: {e}")
        return {"success": False, "error": str(e)}