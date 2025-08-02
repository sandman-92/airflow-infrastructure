"""
Embedding functions for Airflow DAGs.

This module contains reusable embedding functions that are used by DAGs,
separated from the DAG definitions to avoid import issues during testing.
"""

import logging
import json
import sys
import os
from typing import Dict, Any, Optional
import uuid
import random
from datetime import datetime

from openai import OpenAI

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
        dict: Dictionary with exists status, embedding_id, url_id, and json_file_id
    """
    
    if not url_id or not json_file_id:
        raise ValueError("URL_ID and JSON_FILE_ID are required parameters")
    
    logger.info(f"Checking for existing embedding: URL_ID={url_id}, JSON_FILE_ID={json_file_id}")
    
    # Add models directory to path
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'models'))
    from base import SessionLocal
    from model import FullArticleTextEmbedding
    
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
            return {
                'exists': True,
                'embedding_id': existing_embedding.id,
                'url_id': url_id,
                'json_file_id': json_file_id
            }
        else:
            logger.info("No existing embedding found. Proceeding with creation.")
            return {
                'exists': False,
                'embedding_id': None,
                'url_id': url_id,
                'json_file_id': json_file_id
            }
            
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
        dict: The generated embedding result with embedding, url_id, and json_file_id
    """
    if isinstance(check_result, dict) and check_result.get('exists'):
        logger.info("Skipping embedding generation - embedding already exists")
        return {"status": "skipped", "reason": "embedding already exists"}
    
    if not all([text, model]):
        raise ValueError("text and model are required parameters")
    
    logger.info(f"Generating embedding using model: {model}")
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
        
        return {
            'embedding': embedding_vector,
            'url_id': check_result.get('url_id') if isinstance(check_result, dict) else None,
            'json_file_id': check_result.get('json_file_id') if isinstance(check_result, dict) else None
        }
        
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
    
    # Extract embedding vector from result
    if isinstance(embedding_result, dict) and 'embedding' in embedding_result:
        embedding_vector = embedding_result['embedding']
    elif isinstance(embedding_result, str):
        embedding_vector = json.loads(embedding_result)
    else:
        raise ValueError(f"Invalid embedding_result format: {type(embedding_result)}")
    
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
        
        # Add models directory to path
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'models'))
        from base import SessionLocal
        from model import FullArticleTextEmbedding
        
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