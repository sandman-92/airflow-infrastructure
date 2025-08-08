import sys
import os

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, TIMESTAMP
from sqlalchemy.orm import relationship
from datetime import datetime


# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from base import Base, engine

class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, nullable=False, index=True)
    json_file_path = Column(String, nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    embeddings = relationship("Embedding", back_populates="url", cascade="all, delete-orphan")


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    url_id = Column(Integer, ForeignKey("urls.id", ondelete="CASCADE"), nullable=False)
    collection = Column(String, nullable=False)
    qdrant_index = Column(String, nullable=True)


    created_at = Column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    url = relationship("URL", back_populates="embeddings")

# Create all tables
def create_tables():
    """Create all tables in the database"""
    # from base import engine
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables from the database"""
    # from .base import engine
    Base.metadata.drop_all(bind=engine)