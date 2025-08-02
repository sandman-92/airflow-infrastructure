# DAG Testing Framework

This directory contains a comprehensive testing framework for Apache Airflow DAGs with support for SQLite database testing, OpenAI mocking, and Qdrant mocking.

## Overview

The test framework provides:

- **SQLite Database Testing**: Temporary SQLite databases for each test with automatic setup/teardown
- **OpenAI API Mocking**: Mock OpenAI client for testing embedding generation without API calls
- **Qdrant Client Mocking**: Mock Qdrant client for testing vector database operations
- **Airflow Context Mocking**: Mock Airflow context for testing task functions
- **Helper Utilities**: Database assertion helpers and test utilities

## Quick Start

### Prerequisites

Make sure you have the required dependencies installed:

```bash
poetry install
```

### Running Tests

Run all tests:
```bash
poetry run pytest dag_tests/
```

Run specific test file:
```bash
poetry run pytest dag_tests/test_create_embedding_dag.py
```

Run with verbose output:
```bash
poetry run pytest dag_tests/ -v
```

## Framework Components

### Core Fixtures (conftest.py)

#### `test_db`
Creates a temporary SQLite database for each test with all tables set up.

```python
def test_my_function(test_db):
    engine, SessionLocal, db_path = test_db
    session = SessionLocal()
    
    # Your test code here
    url_record = URLInjestion(url="https://test.com", status="Success")
    session.add(url_record)
    session.commit()
    
    session.close()
```

#### `mock_openai`
Provides a mocked OpenAI client that returns standard embeddings.

```python
def test_embedding_generation(mock_openai):
    from my_dag import generate_embedding
    
    result = generate_embedding("test content", mock_openai, "text-embedding-3-small")
    
    # Verify OpenAI was called
    mock_openai.embeddings.create.assert_called_once()
    assert len(result) == 1536  # Standard embedding size
```

#### `mock_qdrant`
Provides a mocked Qdrant client for vector database operations.

```python
def test_vector_storage(mock_qdrant):
    from my_dag import store_in_qdrant
    
    result = store_in_qdrant(collection="test", vector=[0.1] * 1536)
    
    # Verify Qdrant was called
    mock_qdrant.upsert.assert_called_once()
```

#### `sample_data`
Creates sample database records for testing.

```python
def test_with_sample_data(sample_data):
    data = sample_data
    
    # Access pre-created records
    url_record = data['url_record']
    json_record = data['json_record']
    embedding_record = data['embedding_record']
    session = data['session']
```

#### `mock_airflow_context`
Provides a mocked Airflow context for testing task functions.

```python
def test_airflow_task(mock_airflow_context):
    from my_dag import my_task_function
    
    result = my_task_function()
    
    # Context is automatically available via get_current_context()
```

### Helper Functions

#### Database Assertions

```python
from conftest import assert_database_record_exists, assert_database_record_count

def test_database_operations(test_db):
    engine, SessionLocal, db_path = test_db
    session = SessionLocal()
    
    # Assert record exists
    record = assert_database_record_exists(
        session, URLInjestion, url="https://test.com"
    )
    
    # Assert record count
    assert_database_record_count(session, URLInjestion, 1)
    
    session.close()
```

## Writing Tests

### Basic DAG Test Structure

```python
import pytest
import sys
import os

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dags'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'models'))

from airflow.models import DagBag
from models.model import URLInjestion, JsonFiles, FullArticleTextEmbedding


class TestMyDAG:
    """Test cases for my_dag.py"""

    def test_dag_loaded(self):
        """Test that the DAG can be loaded successfully."""
        dagbag = DagBag(dag_folder="dags", include_examples=False)
        dag = dagbag.get_dag(dag_id="my_dag")
        
        assert dag is not None
        assert len(dag.tasks) > 0

    def test_my_function(self, test_db, mock_openai, mock_qdrant):
        """Test individual DAG functions."""
        from my_dag import my_function
        
        engine, SessionLocal, db_path = test_db
        
        result = my_function(test_param="value")
        
        assert result is not None
        # Add your assertions here
```

### Testing Database Operations

```python
def test_database_function(self, test_db):
    """Test functions that interact with the database."""
    from my_dag import database_function
    
    engine, SessionLocal, db_path = test_db
    
    # Call function that uses database
    result = database_function()
    
    # Verify database changes
    session = SessionLocal()
    assert_database_record_count(session, URLInjestion, 1)
    session.close()
```

### Testing OpenAI Integration

```python
def test_openai_function(self, mock_openai):
    """Test functions that use OpenAI."""
    from my_dag import generate_embedding
    
    result = generate_embedding("test content", mock_openai, "text-embedding-3-small")
    
    # Verify OpenAI was called correctly
    mock_openai.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input="test content"
    )
    
    # Verify result
    assert len(result) == 1536
```

### Testing Qdrant Integration

```python
def test_qdrant_function(self, mock_qdrant):
    """Test functions that use Qdrant."""
    from my_dag import store_vector
    
    result = store_vector("collection", [0.1] * 1536)
    
    # Verify Qdrant was called
    mock_qdrant.upsert.assert_called_once()
    
    # Verify result
    assert result['success'] is True
```

### Full Integration Tests

```python
def test_full_workflow(self, test_db, mock_openai, mock_qdrant):
    """Test complete workflow with all components."""
    from my_dag import workflow_function
    
    engine, SessionLocal, db_path = test_db
    
    # Run complete workflow
    result = workflow_function()
    
    # Verify all components were used
    mock_openai.embeddings.create.assert_called()
    mock_qdrant.upsert.assert_called()
    
    # Verify database state
    session = SessionLocal()
    assert_database_record_count(session, FullArticleTextEmbedding, 1)
    session.close()
```

## Best Practices

### Test Organization

1. **One test file per DAG**: Create `test_my_dag.py` for `my_dag.py`
2. **Group related tests**: Use classes to group related test methods
3. **Descriptive test names**: Use clear, descriptive test method names

### Database Testing

1. **Use fixtures**: Always use the `test_db` fixture for database tests
2. **Clean sessions**: Always close database sessions in tests
3. **Test isolation**: Each test gets a fresh database
4. **Verify state**: Use assertion helpers to verify database state

### Mocking

1. **Use provided fixtures**: Use `mock_openai` and `mock_qdrant` fixtures
2. **Verify calls**: Always verify that mocked services were called correctly
3. **Configure responses**: Customize mock responses for specific test scenarios

### Error Testing

1. **Test error conditions**: Test how functions handle errors
2. **Test rollbacks**: Verify database rollbacks work correctly
3. **Test edge cases**: Test boundary conditions and edge cases

## Example Test Files

- `test_create_embedding_dag.py`: Comprehensive example testing OpenAI, Qdrant, and database operations
- `test_database_migration_dag.py`: Database-focused testing example

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure paths are added correctly in test files
2. **Database connection errors**: The framework automatically handles database URLs
3. **Mock not working**: Ensure you're using the correct fixture names

### Running Individual Tests

```bash
# Run specific test method
poetry run pytest dag_tests/test_my_dag.py::TestMyDAG::test_my_function

# Run with debugging output
poetry run pytest dag_tests/ -v -s

# Run with coverage
poetry run pytest dag_tests/ --cov=dags
```

## Framework Validation

The framework includes self-validation tests in `TestFrameworkValidation` classes that verify:

- Database isolation works correctly
- Mocks are properly configured
- Fixtures provide expected data
- Cleanup happens automatically

Run these tests to verify the framework is working correctly:

```bash
poetry run pytest dag_tests/ -k "TestFrameworkValidation"
```