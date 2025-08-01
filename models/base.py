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