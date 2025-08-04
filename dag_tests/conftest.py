"""
Test configuration and fixtures for DAG testing framework.

This module provides:
- SQLite database setup/teardown for testing
- OpenAI API mocking utilities
- Qdrant client mocking utilities
- Base test fixtures and utilities
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

# Add models to path for imports
import sys
root_dir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(root_dir)


from models.base import Base, get_current_engine
from models.model import (
    TaskStatus,
    URLInjestion,
    JsonFiles,
    FullArticleTextEmbedding,
    URLKeyWordTable,
    GdeltKeywords
)


@pytest.fixture(scope="function")
def test_db():
    """
    Create a temporary SQLite database for testing, using SQLAlchemy models directly.

    Returns:
        tuple: (engine, SessionLocal, db_path)
    """
    # Store original env var
    original_db_url = os.environ.get('APP_DATABASE_URL')

    # Create temp database file
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)

    sqlite_url = f"sqlite:///{db_path}"
    os.environ['APP_DATABASE_URL'] = sqlite_url

    # Create engine using the current environment variable
    engine = get_current_engine()
    
    # Import models to ensure they're registered with Base
    from models import model
    
    # Get the Base instance that the models are actually using
    models_base = model.Base
    
    # Create all tables using the models' Base.metadata.create_all with the test engine
    models_base.metadata.create_all(engine)

    # Session factory
    SessionLocal = sessionmaker(bind=engine)

    yield engine, SessionLocal, db_path

    # Cleanup env
    if original_db_url:
        os.environ['APP_DATABASE_URL'] = original_db_url
    elif 'APP_DATABASE_URL' in os.environ:
        del os.environ['APP_DATABASE_URL']

    # Remove temp DB file
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(scope="function")
def mock_openai():
    """
    Mock OpenAI client for testing.
    
    This fixture provides a mock OpenAI client that can be configured
    to return specific responses for testing embedding generation.
    
    Returns:
        Mock: Configured OpenAI client mock
    """
    with patch('openai.OpenAI') as mock_client_class:
        # Create mock client instance
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock embeddings.create method
        mock_embedding_response = Mock()
        mock_embedding_response.data = [Mock()]
        mock_embedding_response.data[0].embedding = [0.1] * 1536  # Standard OpenAI embedding size
        
        mock_client.embeddings.create.return_value = mock_embedding_response
        
        yield mock_client


@pytest.fixture(scope="function")
def mock_qdrant():
    """
    Mock Qdrant client for testing.
    
    This fixture provides a mock Qdrant client that can be configured
    to simulate vector database operations.
    
    Returns:
        Mock: Configured Qdrant client mock
    """
    with patch('qdrant_client.QdrantClient') as mock_client_class:
        # Create mock client instance
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock common Qdrant operations
        mock_client.upsert.return_value = Mock(operation_id=1, status="completed")
        mock_client.search.return_value = []
        mock_client.get_collection.return_value = Mock(status="green")
        mock_client.create_collection.return_value = True
        
        yield mock_client


@pytest.fixture(scope="function")
def sample_data(test_db):
    """
    Create sample data for testing.
    
    This fixture creates sample records in the test database
    that can be used by tests.
    
    Args:
        test_db: Database fixture
        
    Returns:
        dict: Dictionary containing created sample data
    """
    engine, SessionLocal, db_path = test_db
    session = SessionLocal()
    
    try:
        # Create sample URL ingestion record
        url_record = URLInjestion(
            url="https://example.com/test-article",
            status="Success"
        )
        session.add(url_record)
        session.commit()
        session.refresh(url_record)
        
        # Create sample JSON file record
        json_record = JsonFiles(
            filepath="/tmp/test_article.json",
            status="Success",
            url_id=url_record.id
        )
        session.add(json_record)
        session.commit()
        session.refresh(json_record)
        
        # Create sample embedding record
        embedding_record = FullArticleTextEmbedding(
            url_id=url_record.id,
            json_file_id=json_record.id,
            qdrant_collection="test_collection",
            qdrant_index="test_index_123",
            status="Success"
        )
        session.add(embedding_record)
        session.commit()
        session.refresh(embedding_record)
        
        # Don't close session here - let the test handle it
        return {
            'url_record': url_record,
            'json_record': json_record,
            'embedding_record': embedding_record,
            'session': session
        }
    
    except Exception as e:
        session.rollback()
        session.close()
        raise e


@pytest.fixture(scope="function")
def mock_airflow_context():
    """
    Mock Airflow context for testing task functions.
    
    This fixture provides a mock Airflow context that can be used
    to test task functions that depend on Airflow context.
    
    Returns:
        Mock: Configured Airflow context mock
    """
    context = {
        'dag': Mock(),
        'task': Mock(),
        'task_instance': Mock(),
        'execution_date': Mock(),
        'ds': '2025-08-01',
        'ds_nodash': '20250801',
        'ti': Mock()
    }
    
    # Configure task instance mock
    context['ti'].xcom_pull = Mock(return_value=None)
    context['ti'].xcom_push = Mock()
    
    with patch('airflow.operators.python.get_current_context', return_value=context):
        yield context


class TestFrameworkError(Exception):
    """Custom exception for test framework errors."""
    pass


def assert_database_record_exists(session, model_class, **kwargs):
    """
    Helper function to assert that a database record exists.
    
    Args:
        session: Database session
        model_class: SQLAlchemy model class
        **kwargs: Filter criteria
        
    Raises:
        AssertionError: If record doesn't exist
    """
    record = session.query(model_class).filter_by(**kwargs).first()
    assert record is not None, f"Expected {model_class.__name__} record with {kwargs} not found"
    return record


def assert_database_record_count(session, model_class, expected_count, **kwargs):
    """
    Helper function to assert the count of database records.
    
    Args:
        session: Database session
        model_class: SQLAlchemy model class
        expected_count: Expected number of records
        **kwargs: Filter criteria
        
    Raises:
        AssertionError: If count doesn't match
    """
    query = session.query(model_class)
    if kwargs:
        query = query.filter_by(**kwargs)
    
    actual_count = query.count()
    assert actual_count == expected_count, f"Expected {expected_count} {model_class.__name__} records, found {actual_count}"