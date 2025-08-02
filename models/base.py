from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database URL - can be overridden by environment variable
APP_DATABASE_URL = os.getenv("APP_DATABASE_URL", "postgresql://app_user:app_password@postgres_app:5432/app_db")

# Create SQLAlchemy engine
engine = create_engine(APP_DATABASE_URL)

# Create declarative base
Base = declarative_base()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_current_engine():
    """
    Get a database engine based on current environment variables.
    This function creates a fresh engine each time, respecting any changes
    to the APP_DATABASE_URL environment variable.
    """
    current_db_url = os.getenv("APP_DATABASE_URL", "postgresql://app_user:app_password@postgres_app:5432/app_db")
    return create_engine(current_db_url)


def get_current_session():
    """
    Get a database session based on current environment variables.
    This function creates a fresh session factory each time, respecting any changes
    to the APP_DATABASE_URL environment variable.
    """
    current_engine = get_current_engine()
    CurrentSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=current_engine)
    return CurrentSessionLocal()