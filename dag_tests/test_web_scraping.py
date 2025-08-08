import sys
import os
import pytest
import unittest
from conftest import test_db
from sqlalchemy import inspect

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
# from models.base import SessionLocal
# 👇 Import ALL models explicitly (ensure this includes FullArticleTextEmbedding, etc.)
from models.base import Base
from models.model import (
    URL, Embedding
)


def test_db_tables(test_db):
    """
    this test asserts that all of the tables are in the model.py file and declared
    There must be an up to date migration script in model/alembic/versions
    Args:
        test_db: pytest fixture creating a test db in SQLite

    Returns:
        None
    """

    engine, SessionLocal, db_path = test_db

    with SessionLocal() as session:

        inspector = inspect(session.bind)
        tables = inspector.get_table_names()
        assert "embeddings" in tables
        assert "urls" in tables



