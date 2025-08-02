from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

import sys
import os

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from base import Base, engine


class URLInjestion(Base):
    """
    Table to track URL ingestion status.
    Status values: Queued, Running, Failed, Success
    """
    __tablename__ = "url_injestion"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="Queued")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to JsonFiles
    json_files = relationship("JsonFiles", back_populates="url_injestion")
    
    # Relationship to FullArticleTextEmbedding
    full_article_text_embeddings = relationship("FullArticleTextEmbedding", back_populates="url_injestion")
    
    def __repr__(self):
        return f"<URLInjestion(id={self.id}, url='{self.url}', status='{self.status}')>"


class JsonFiles(Base):
    """
    Table to track JSON file processing status.
    Status values: Queued, Running, Failed, Success
    """
    __tablename__ = "json_files"

    id = Column(Integer, primary_key=True, index=True)
    filepath = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="Queued")
    url_id = Column(Integer, ForeignKey("url_injestion.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to URLInjestion
    url_injestion = relationship("URLInjestion", back_populates="json_files")
    
    # Relationship to FullArticleTextEmbedding
    full_article_text_embeddings = relationship("FullArticleTextEmbedding", back_populates="json_file")
    
    def __repr__(self):
        return f"<JsonFiles(id={self.id}, filepath='{self.filepath}', status='{self.status}')>"


class FullArticleTextEmbedding(Base):
    """
    Table to store full article text embeddings with Qdrant vector collection index.
    Status values: Queued, Running, Failed, Success
    """
    __tablename__ = "full_article_text_embedding"

    id = Column(Integer, primary_key=True, index=True)
    url_id = Column(Integer, ForeignKey("url_injestion.id"), nullable=False)
    json_file_id = Column(Integer, ForeignKey("json_files.id"), nullable=False)
    qdrant_index = Column(String, nullable=True, index=True)
    qdrant_collection = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="Queued")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    url_injestion = relationship("URLInjestion", back_populates="full_article_text_embeddings")
    json_file = relationship("JsonFiles", back_populates="full_article_text_embeddings")
    
    def __repr__(self):
        return f"<FullArticleTextEmbedding(id={self.id}, qdrant_index='{self.qdrant_index}')>"


# Create all tables
def create_tables():
    """Create all tables in the database"""
    # from base import engine
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables from the database"""
    # from .base import engine
    Base.metadata.drop_all(bind=engine)