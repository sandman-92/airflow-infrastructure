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
from sqlalchemy import text


class TaskStatus(Base):
    __tablename__ = "task_status"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    url_injestions = relationship("URLInjestion", back_populates="status")
    json_files = relationship("JsonFiles", back_populates="task_status")


class URLInjestion(Base):
    __tablename__ = "url_injestion"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False, unique=True, index=True)

    status_id = Column(Integer, ForeignKey("task_status.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime(timezone=True), onupdate=text('CURRENT_TIMESTAMP'))

    # Relationships
    status = relationship("TaskStatus", back_populates="url_injestions")
    json_files = relationship("JsonFiles", back_populates="url_injestion")
    full_article_text_embeddings = relationship("FullArticleTextEmbedding", back_populates="url_injestion")
    url_keywords = relationship("URLKeyWordTable", back_populates="url_injestion")
    def __repr__(self):
        return f"<URLInjestion(id={self.id}, item='{self.url}', status_id='{self.status_id}')>"




class JsonFiles(Base):
    """
    Table to track JSON file processing status.
    Status values: Queued, Running, Failed, Success
    """
    __tablename__ = "json_files"

    id = Column(Integer, primary_key=True, index=True)
    filepath = Column(String, nullable=False, unique=True, index=True)
    status_id = Column(Integer, ForeignKey("task_status.id"))
    url_id = Column(Integer, ForeignKey("url_injestion.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime(timezone=True), onupdate=text('CURRENT_TIMESTAMP'))
    
    # Relationship to URLInjestion
    url_injestion = relationship("URLInjestion", back_populates="json_files")

    #Relationship to task_status
    task_status = relationship("TaskStatus", back_populates="json_files")
    
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
    qdrant_collection = Column(String, nullable=True, index=True)
    status_id = Column(Integer, ForeignKey("task_status.id"))
    created_at = Column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime(timezone=True), onupdate=text('CURRENT_TIMESTAMP'))
    
    # Relationships
    url_injestion = relationship("URLInjestion", back_populates="full_article_text_embeddings")
    json_file = relationship("JsonFiles", back_populates="full_article_text_embeddings")
    
    def __repr__(self):
        return f"<FullArticleTextEmbedding(id={self.id}, qdrant_index='{self.qdrant_index}')>"


class URLKeyWordTable(Base):
    """
    registers which gdelt keywords the URLS are associated with
    """
    __tablename__ = "url_keyword_table"
    id = Column(Integer, primary_key=True, index=True)
    url_id = Column(Integer, ForeignKey("url_injestion.id"), nullable=False)
    keyword_id = Column(Integer, ForeignKey("gdelt_keywords.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime(timezone=True), onupdate=text('CURRENT_TIMESTAMP'))


    #relationships
    url_injestion = relationship("URLInjestion", back_populates="url_keywords")
    gdelt_keyword = relationship("GdeltKeywords", back_populates="url_keywords")


    def __repr__(self):
        return f"<URLKeyWordTable(id={self.id}, url_id={self.url_id}, keyword_id={self.keyword_id})>"

class GdeltKeywords(Base):
    """
    key word search table for gdelt library
    """
    __tablename__ = "gdelt_keywords"
    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime(timezone=True), onupdate=text('CURRENT_TIMESTAMP'))

    #relationships:
    url_keywords = relationship("URLKeyWordTable", back_populates="gdelt_keyword")

    def __repr__(self):
        return f"<GdeltKeywords(id={self.id}, keyword='{self.keyword}')>"

# Create all tables
def create_tables():
    """Create all tables in the database"""
    # from base import engine
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables from the database"""
    # from .base import engine
    Base.metadata.drop_all(bind=engine)