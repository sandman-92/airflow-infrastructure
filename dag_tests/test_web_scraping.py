import sys
import os
import pytest
import unittest
from conftest import test_db
from sqlalchemy import inspect

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from dags.web_scraping_dag import check_and_update_database
# from models.base import SessionLocal



# def test_db_tables(test_db):
#     """
#     this test asserts that all of the tables are in the model.py file and declared
#     There must be an up to date migration script in model/alembic/versions
#     Args:
#         test_db: pytest fixture creating a test db in SQLite
#
#     Returns:
#         None
#     """
#
#     engine, SessionLocal, db_path = test_db
#
#     with SessionLocal() as session:
#
#         inspector = inspect(session.bind)
#         tables = inspector.get_table_names()
#         assert "full_article_text_embedding" in tables
#         assert "gdelt_keywords" in tables
#         assert "url_injestion" in tables
#         assert "json_files" in tables
#         assert "task_status" in tables
#         assert "url_keyword_table"
#
#
# def test_db_checker_url(test_db):
#     """
#     checks to see if a url does not exist it changes the Trigger Conf to true, if the url does exist the trigger is false
#     Args:
#         test_db:
#
#     Returns:
#
#     """
#     #Create a new test_db and SessionLocal
#     engine, SessionLocal, db_path = test_db
#
#     #check that if a url does not exist, it adds it and sets Trigger to true
#     conf = {}
#     conf['TriggerScraper'] = True
#     conf['url'] = "https://fakeurl.com"
#
#     with SessionLocal() as session:
#
#         conf = check_and_update_database(config=conf, task_to_run="scraping", session = session)
#     assert conf['TriggerScraper'] is True
#
#     #Try add the same URL to the db should return false
#     with SessionLocal() as session:
#
#         conf = check_and_update_database(config=conf, task_to_run="scraping", session = session)
#     assert conf['TriggerScraper'] is False
#
#
# def test_db_checker_json(test_db):
#     """
#     checks to see if a json file does not exist it changes the Trigger Conf to true, if the json does exist the trigger is false
#     Args:
#         test_db:
#
#     Returns:
#
#     """
#     #Create a new test_db and SessionLocal
#     engine, SessionLocal, db_path = test_db
#
#     #check that if a url does not exist, it adds it and sets Trigger to true
#     conf = {}
#     conf['TriggerJson'] = True
#     conf['url'] = "https://fakeurl.com"
#     conf['filepath'] = "fake_file.json"
#
#     #add the url to the url table
#     with SessionLocal() as session:
#         conf = check_and_update_database(config=conf, task_to_run="scraping", session = session)
#
#
#     # Check to see if json will be triggered
#     with SessionLocal() as session:
#         conf = check_and_update_database(config=conf, task_to_run="writejson", session = session)
#     assert conf['TriggerJson'] is True
#
#     #Try add the same json file
#     with SessionLocal() as session:
#         conf = check_and_update_database(config=conf, task_to_run="writejson", session = session)
#     assert conf['TriggerJson'] is False
#

def test_db_checker_embedding(test_db):
    """
    checks to see if a json file does not exist it changes the Trigger Conf to true, if the json does exist the trigger is false
    Args:
        test_db:

    Returns:

    """
    #Create a new test_db and SessionLocal
    engine, SessionLocal, db_path = test_db

    #check that if a url does not exist, it adds it and sets Trigger to true
    conf = {}
    conf['TriggerEmbedding'] = True
    conf['url'] = "https://fakeurl.com"
    conf['filepath'] = "fake_file.json"

    #add the url to the url table
    with SessionLocal() as session:
        conf = check_and_update_database(config=conf, task_to_run="scraping", session = session)

    #add the json file to the json file table
    with SessionLocal() as session:
        conf = check_and_update_database(config=conf, task_to_run="writejson", session=session)


    # Check to see if embedding will be triggered
    with SessionLocal() as session:
        conf = check_and_update_database(config=conf, task_to_run="embedding", session = session)
    assert conf['TriggerEmbedding'] is True

    #Try add the same json file
    with SessionLocal() as session:
        conf = check_and_update_database(config=conf, task_to_run="embedding", session = session)
    assert conf['TriggerEmbedding'] is False



