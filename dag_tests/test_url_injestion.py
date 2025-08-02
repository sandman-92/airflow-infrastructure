import os
import sys
from unittest.mock import patch

# Add dags directory to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dags_path = os.path.join(project_root, "dags")
sys.path.insert(0, dags_path)

# Add models to path for imports
models_path = os.path.join(project_root, "models")
sys.path.insert(0, models_path)

# Import after path modifications to avoid import errors
from conftest import (  # noqa: E402
    assert_database_record_count,
    assert_database_record_exists,
)
from model import URLInjestion  # noqa: E402
from web_scraping_dag import scrape_url_task  # noqa: E402


def test_url_injestion(test_db):
    """
    Test the scrape_url_task function with three URLs.

    This test:
    1. Mocks the requests library to return sample scraped data
    2. Calls scrape_url_task with three different URLs
    3. Asserts that the correct data is returned
    4. Asserts that all three URLs are added to the database with correct
       status
    """
    engine, SessionLocal, db_path = test_db
    session = SessionLocal()

    # Test URLs
    test_urls = [
        "https://example.com/article1",
        "https://example.com/article2",
        "https://example.com/article3",
    ]

    # Expected scraped data for each URL
    expected_data = [
        {
            "title": "Test Article 1",
            "text": "This is the content of test article 1. "
            * 50,  # Make it > 1000 chars
            "url": test_urls[0],
        },
        {
            "title": "Test Article 2",
            "text": "This is the content of test article 2. "
            * 50,  # Make it > 1000 chars
            "url": test_urls[1],
        },
        {
            "title": "Test Article 3",
            "text": "This is the content of test article 3. "
            * 50,  # Make it > 1000 chars
            "url": test_urls[2],
        },
    ]

    try:
        # Mock the SessionLocal to use our test database session
        with patch("web_scraping_dag.SessionLocal", return_value=session):
            # Mock the scrape_with_requests function to return our test data
            with patch("web_scraping_dag.scrape_with_requests") as mock_scrape:
                # Configure mock to return different data based on URL
                def mock_scrape_side_effect(url):
                    for i, test_url in enumerate(test_urls):
                        if url == test_url:
                            return expected_data[i]
                    return None

                mock_scrape.side_effect = mock_scrape_side_effect

                # Test scraping each URL
                results = []
                for i, url in enumerate(test_urls):
                    result = scrape_url_task(url, retry_url_config=False)
                    results.append(result)

                    # Assert the returned data matches expected
                    assert result is not None, (
                        f"Expected data for URL {url}, got None"
                    )
                    assert (
                        result["title"] == expected_data[i]["title"]
                    ), f"Title mismatch for URL {url}"
                    assert (
                        result["text"] == expected_data[i]["text"]
                    ), f"Text mismatch for URL {url}"
                    assert (
                        result["url"] == expected_data[i]["url"]
                    ), f"URL mismatch for URL {url}"

                # Assert all three URLs were added to the database
                assert_database_record_count(session, URLInjestion, 3)

                # Assert each URL exists in database with Success status
                for url in test_urls:
                    record = assert_database_record_exists(
                        session, URLInjestion, url=url, status="Success"
                    )
                    assert record.url == url, (
                        f"Database record URL mismatch for {url}"
                    )
                    assert (
                        record.status == "Success"
                    ), (
                        f"Expected Success status for {url}, "
                        f"got {record.status}"
                    )

                # Verify mock was called correctly
                assert (
                    mock_scrape.call_count == 3
                ), (
                    f"Expected 3 calls to scrape_with_requests, "
                    f"got {mock_scrape.call_count}"
                )

    finally:
        session.close()
