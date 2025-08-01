"""
DAG for creating text embeddings and storing them in Qdrant vector database.

This DAG is designed to be triggered with variables from the web scraping DAG
but can also be run independently for testing purposes.

Required Variables:
- QdrantCollection: The Qdrant collection name (default: FullTextEmbedding)
- URL_ID: The URL ID from the URLInjestion table
- JSON_FILE_ID: The JSON file ID from the JsonFiles table
- retry_embedding: Boolean to retry if embedding already exists (default: False)
- text: The text content to embed
- client: The embedding client/service to use
- model: The embedding model to use
"""

from datetime import datetime, timedelta
import logging
import json
import sys
import os
from typing import Dict, Any, Optional
import uuid
import random

from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable
from airflow.operators.python import get_current_context
from openai import OpenAI

# Add models directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'models'))
from base import SessionLocal
from model import FullArticleTextEmbedding

# Configure logging
logger = logging.getLogger(__name__)






def check_embedding_exists(url_id, json_file_id):
    """
    Check if an embedding already exists for the given URL_ID and JSON_FILE_ID.
    If an embedding exists, the workflow will be skipped.
    
    Args:
        url_id: The URL ID from the URLInjestion table
        json_file_id: The JSON file ID from the JsonFiles table
    
    Returns:
        str: 'skip' if embedding exists, 'proceed' if no embedding found
    """
    
    if not url_id or not json_file_id:
        raise ValueError("URL_ID and JSON_FILE_ID are required parameters")
    
    logger.info(f"Checking for existing embedding: URL_ID={url_id}, JSON_FILE_ID={json_file_id}")
    
    # Query database for existing embedding
    session = SessionLocal()
    try:
        existing_embedding = session.query(FullArticleTextEmbedding).filter(
            FullArticleTextEmbedding.url_id == url_id,
            FullArticleTextEmbedding.json_file_id == json_file_id
        ).first()
        
        if existing_embedding:
            logger.info(f"Found existing embedding with ID: {existing_embedding.id}, Status: {existing_embedding.status}")
            logger.info("Skipping workflow - embedding already exists")
            return 'skip'
        else:
            logger.info("No existing embedding found. Proceeding with creation.")
            return 'proceed'
            
    except Exception as e:
        logger.error(f"Error checking embedding existence: {str(e)}")
        raise
    finally:
        session.close()


def generate_embedding(content: str, client: OpenAI, model: str):
    """
    Generate embedding using OpenAI API with test mode support.
    
    Args:
        content (str): The text content to embed
        client (OpenAI): The OpenAI client instance
        model (str): The embedding model to use
        
    Returns:
        list: The embedding vector as a list of floats
    """
    test_mode = os.getenv("TEST_MODE", "False").lower() in ("1", "True", "yes")
    if test_mode:
        return [round(random.uniform(-1, 1), 4) for _ in range(384)]
    else:
        response = client.embeddings.create(
            model=model,
            input=content,
        )
        return response.data[0].embedding


def generate_text_embedding(check_result, text, model):
    """
    Generate text embedding using the specified client and model.
    
    Args:
        check_result: Result from the check_embedding_exists task
        text: The text content to embed
        model: The embedding model to use
    
    Returns:
        str: The generated embedding as a JSON string, or dict with skip status
    """
    if check_result == 'skip':
        logger.info("Skipping embedding generation - embedding already exists")
        return {"status": "skipped", "reason": "embedding already exists"}
    
    if not all([text,  model]):
        raise ValueError("text, and model are required parameters")
    
    logger.info(f"Generating embedding using  model: {model}")
    logger.info(f"Text length: {len(text)} characters")
    
    try:
        # Initialize OpenAI client using environment variable
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        client = OpenAI(api_key=api_key)
        
        # Generate embedding using the helper function
        embedding_vector = generate_embedding(text, client, model)
        
        logger.info(f"Generated embedding with {len(embedding_vector)} dimensions")
        return json.dumps(embedding_vector)
        
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise


def store_embedding_in_qdrant(url_id, json_file_id, qdrant_collection, embedding_result):
    """
    Store the generated embedding in Qdrant vector database and update database status to Success.
    
    Args:
        url_id: The URL ID from the URLInjestion table
        json_file_id: The JSON file ID from the JsonFiles table
        qdrant_collection: The Qdrant collection name
        embedding_result: The embedding result from the previous task
    
    Returns:
        dict: Success status with point ID and collection name, or skip status
    """
    
    # More robust validation for embedding_result
    if embedding_result is None:
        raise ValueError("No embedding data received from previous task")
    
    # Handle empty string case
    if isinstance(embedding_result, str) and not embedding_result.strip():
        raise ValueError("Empty embedding data received from previous task")
    
    # Check if embedding generation was skipped
    if isinstance(embedding_result, dict) and embedding_result.get('status') == 'skipped':
        logger.info("Embedding generation was skipped, no Qdrant storage needed")
        return {"status": "skipped", "reason": "embedding generation was skipped"}
    
    embedding_vector = json.loads(embedding_result)
    
    logger.info(f"Storing embedding in Qdrant collection: {qdrant_collection}")
    logger.info(f"Embedding dimensions: {len(embedding_vector)}")
    
    try:
        
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
        
        # Connect to Qdrant (using docker-compose service name)
        client = QdrantClient(host="qdrant", port=6333)
        
        # Ensure collection exists
        try:
            client.get_collection(qdrant_collection)
            logger.info(f"Collection {qdrant_collection} already exists")
        except Exception:
            # Create collection if it doesn't exist
            client.create_collection(
                collection_name=qdrant_collection,
                vectors_config=VectorParams(size=len(embedding_vector), distance=Distance.COSINE)
            )
            logger.info(f"Created collection {qdrant_collection}")
        
        # Generate unique point ID
        point_id = str(uuid.uuid4())
        
        # Create point with metadata
        point = PointStruct(
            id=point_id,
            vector=embedding_vector,
            payload={
                "url_id": url_id,
                "json_file_id": json_file_id,
                "created_at": datetime.now().isoformat()
            }
        )
        
        # Insert point into collection
        client.upsert(
            collection_name=qdrant_collection,
            points=[point]
        )
        
        logger.info(f"Successfully stored embedding in Qdrant with point ID: {point_id}")
        
        # Update database status to Success
        logger.info(f"Updating database status to Success for URL_ID: {url_id}, JSON_FILE_ID: {json_file_id}")
        
        session = SessionLocal()
        try:
            # Find or create the embedding record
            embedding_record = session.query(FullArticleTextEmbedding).filter(
                FullArticleTextEmbedding.url_id == url_id,
                FullArticleTextEmbedding.json_file_id == json_file_id
            ).first()
            
            if not embedding_record:
                # Create new record if it doesn't exist
                embedding_record = FullArticleTextEmbedding(
                    url_id=url_id,
                    json_file_id=json_file_id,
                    qdrant_collection=qdrant_collection,
                    qdrant_index=point_id,
                    status='Success'
                )
                session.add(embedding_record)
                logger.info("Created new embedding record with Success status")
            else:
                # Update existing record
                embedding_record.qdrant_index = point_id
                embedding_record.qdrant_collection = qdrant_collection
                embedding_record.status = 'Success'
                logger.info(f"Updated existing embedding record ID: {embedding_record.id} with Success status")
            
            session.commit()
            
        except Exception as db_error:
            session.rollback()
            logger.error(f"Error updating database status: {str(db_error)}")
            # Don't raise here - Qdrant storage was successful
        finally:
            session.close()
        
        return {
            "status": "success",
            "point_id": point_id,
            "qdrant_collection": qdrant_collection
        }
        
    except Exception as e:
        logger.error(f"Error storing embedding in Qdrant: {str(e)}")
        raise


# Default DAG arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 8, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
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
        # Context should be extracted in the task decorator
        context = get_current_context()
        dag_run = context['dag_run']
        conf = dag_run.conf or {}
        
        url_id = conf.get('URL_ID')
        json_file_id = conf.get('JSON_FILE_ID')
        
        return check_embedding_exists(url_id, json_file_id)

    @task()
    def generate_text_embedding_task():
        # Context should be extracted in the task decorator
        context = get_current_context()
        ti = context['ti']
        dag_run = context['dag_run']
        conf = dag_run.conf or {}
        
        # Get result from previous task
        check_result = ti.xcom_pull(task_ids='check_embedding_exists')
        
        # Get configuration parameters
        text = conf.get('text')
        model = conf.get('model', "text-embedding-3-small")
        
        return generate_text_embedding(check_result, text, model)

    @task()
    def store_embedding_in_qdrant_task():
        # Context should be extracted in the task decorator
        context = get_current_context()
        ti = context['ti']
        dag_run = context['dag_run']
        conf = dag_run.conf or {}
        
        # Get configuration parameters
        url_id = conf.get('URL_ID')
        json_file_id = conf.get('JSON_FILE_ID')
        qdrant_collection = conf.get('QdrantCollection', 'FullTextEmbedding')
        
        # Get embedding from previous task
        embedding_result = ti.xcom_pull(task_ids='generate_text_embedding')
        
        return store_embedding_in_qdrant(url_id, json_file_id, qdrant_collection, embedding_result)

    # DAG flow
    check_task = check_embedding_exists_task()
    generate_task = generate_text_embedding_task()
    store_task = store_embedding_in_qdrant_task()

    # Set dependencies
    check_task >> generate_task >> store_task