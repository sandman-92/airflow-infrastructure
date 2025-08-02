import os
import sys
import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timedelta
import requests

# Add dags directory to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dags_path = os.path.join(project_root, "dags")
sys.path.insert(0, dags_path)

# Import after path modifications to avoid import errors
from conftest import test_db  # noqa: E402


class TestGdeltUrlInjestionDAG:
    """Test suite for GDelt URL Injestion DAG"""

    def test_dag_loaded(self):
        """Test that the DAG can be loaded successfully"""
        # Import the DAG module directly to avoid database issues
        import gdelt_url_injestion_dag
        
        # Get the DAG from the module
        dag = gdelt_url_injestion_dag.dag
        
        assert dag is not None, "DAG should be loaded successfully"
        assert len(dag.tasks) == 3, f"Expected 3 tasks, got {len(dag.tasks)}"
        
        # Check task IDs
        task_ids = [task.task_id for task in dag.tasks]
        expected_task_ids = [
            "validate_configuration_task",
            "fetch_gdelt_data_task", 
            "inject_urls_task"
        ]
        
        for expected_id in expected_task_ids:
            assert expected_id in task_ids, f"Task {expected_id} not found in DAG"

    def test_dag_structure_and_dependencies(self):
        """Test DAG structure and task dependencies"""
        # Import the DAG module directly to avoid database issues
        import gdelt_url_injestion_dag
        
        # Get the DAG from the module
        dag = gdelt_url_injestion_dag.dag
        
        # Test DAG properties
        assert dag.dag_id == "gdelt_url_injestion_dag"
        assert dag.schedule == "*/10 * * * *"
        assert dag.catchup is False
        assert "gdelt" in dag.tags
        assert "url-injestion" in dag.tags
        assert "scheduled" in dag.tags
        
        # Test task dependencies
        validate_task = dag.get_task("validate_configuration_task")
        fetch_task = dag.get_task("fetch_gdelt_data_task")
        inject_task = dag.get_task("inject_urls_task")
        
        # Check downstream dependencies
        assert "fetch_gdelt_data_task" in validate_task.downstream_task_ids
        assert "inject_urls_task" in fetch_task.downstream_task_ids
        
        # Check upstream dependencies
        assert "validate_configuration_task" in fetch_task.upstream_task_ids
        assert "fetch_gdelt_data_task" in inject_task.upstream_task_ids


class TestGdeltFunctions:
    """Test suite for GDelt functions"""

    @patch('functions.gdelt_functions.Variable')
    def test_validate_gdelt_configuration_success(self, mock_variable):
        """Test successful configuration validation"""
        from functions.gdelt_functions import validate_gdelt_configuration
        
        # Mock Variable.get calls
        def mock_get(key, default_var=None):
            if key == "gdelt_keywords":
                return "climate change, renewable energy, sustainability"
            elif key == "gdelt_api_endpoint":
                return "https://api.gdeltproject.org/api/v2/doc/doc"
            elif key == "gdelt_max_urls_per_run":
                return "50"
            elif key == "gdelt_time_window_hours":
                return "2"
            return default_var
        
        mock_variable.get.side_effect = mock_get
        
        config = validate_gdelt_configuration()
        
        assert config["keywords"] == ["climate change", "renewable energy", "sustainability"]
        assert config["api_endpoint"] == "https://api.gdeltproject.org/api/v2/doc/doc"
        assert config["max_urls_per_run"] == 50
        assert config["time_window_hours"] == 2

    @patch('functions.gdelt_functions.Variable')
    def test_validate_gdelt_configuration_missing_keywords(self, mock_variable):
        """Test configuration validation with missing keywords"""
        from functions.gdelt_functions import validate_gdelt_configuration
        
        # Mock Variable.get to return None for keywords
        def mock_get(key, default_var=None):
            if key == "gdelt_keywords":
                return None
            elif key == "gdelt_api_endpoint":
                return "https://api.gdeltproject.org/api/v2/doc/doc"
            return default_var
        
        mock_variable.get.side_effect = mock_get
        
        with pytest.raises(ValueError, match="gdelt_keywords Variable is required"):
            validate_gdelt_configuration()

    @patch('functions.gdelt_functions.Variable')
    def test_validate_gdelt_configuration_empty_keywords(self, mock_variable):
        """Test configuration validation with empty keywords"""
        from functions.gdelt_functions import validate_gdelt_configuration
        
        # Mock Variable.get to return empty string for keywords
        def mock_get(key, default_var=None):
            if key == "gdelt_keywords":
                return "   ,  ,   "  # Empty keywords after splitting
            elif key == "gdelt_api_endpoint":
                return "https://api.gdeltproject.org/api/v2/doc/doc"
            return default_var
        
        mock_variable.get.side_effect = mock_get
        
        with pytest.raises(ValueError, match="gdelt_keywords must contain at least one keyword"):
            validate_gdelt_configuration()

    @patch('functions.gdelt_functions.Variable')
    def test_validate_gdelt_configuration_missing_endpoint(self, mock_variable):
        """Test configuration validation with missing API endpoint"""
        from functions.gdelt_functions import validate_gdelt_configuration
        
        # Mock Variable.get to return None for endpoint
        def mock_get(key, default_var=None):
            if key == "gdelt_keywords":
                return "climate change"
            elif key == "gdelt_api_endpoint":
                return None
            return default_var
        
        mock_variable.get.side_effect = mock_get
        
        with pytest.raises(ValueError, match="gdelt_api_endpoint Variable is required"):
            validate_gdelt_configuration()

    @patch('functions.gdelt_functions.requests')
    def test_fetch_gdelt_urls_success(self, mock_requests):
        """Test successful GDelt URL fetching"""
        from functions.gdelt_functions import fetch_gdelt_urls
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "articles": [
                {"url": "https://example.com/article1", "title": "Article 1"},
                {"url": "https://example.com/article2", "title": "Article 2"}
            ]
        }
        mock_requests.get.return_value = mock_response
        
        keywords = ["climate change", "renewable energy"]
        api_endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"
        time_window_hours = 1
        max_urls_per_run = 100
        
        urls = fetch_gdelt_urls(keywords, api_endpoint, time_window_hours, max_urls_per_run)
        
        # Should get URLs from both keyword calls (2 URLs per keyword = 4 total)
        assert len(urls) == 4
        assert "https://example.com/article1" in urls
        assert "https://example.com/article2" in urls
        
        # Verify API was called twice (once per keyword)
        assert mock_requests.get.call_count == 2
        
        # Verify each call had the correct individual keyword
        call_args_list = mock_requests.get.call_args_list
        assert call_args_list[0][1]["params"]["query"] == "climate change"
        assert call_args_list[1][1]["params"]["query"] == "renewable energy"

    @patch('functions.gdelt_functions.requests')
    def test_fetch_gdelt_urls_alternative_format(self, mock_requests):
        """Test GDelt URL fetching with alternative response format"""
        from functions.gdelt_functions import fetch_gdelt_urls
        
        # Mock API response with alternative format
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "articles": [
                {"url": "https://example.com/alt1", "title": "Alt Article 1"},
                {"url": "https://example.com/alt2", "title": "Alt Article 2"}
            ]
        }
        mock_requests.get.return_value = mock_response
        
        keywords = ["sustainability"]
        api_endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"
        time_window_hours = 2
        max_urls_per_run = 50
        
        urls = fetch_gdelt_urls(keywords, api_endpoint, time_window_hours, max_urls_per_run)
        
        assert len(urls) == 2
        assert "https://example.com/alt1" in urls
        assert "https://example.com/alt2" in urls
        
        # Verify API was called once (one keyword)
        assert mock_requests.get.call_count == 1

    @patch('functions.gdelt_functions.requests')
    def test_fetch_gdelt_urls_max_limit(self, mock_requests):
        """Test GDelt URL fetching uses max_urls_per_run as maxrecords parameter"""
        from functions.gdelt_functions import fetch_gdelt_urls
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "articles": [
                {"url": f"https://example.com/article{i}", "title": f"Article {i}"}
                for i in range(1, 4)  # 3 articles
            ]
        }
        mock_requests.get.return_value = mock_response
        
        keywords = ["test"]
        api_endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"
        time_window_hours = 1
        max_urls_per_run = 5  # This becomes the maxrecords parameter
        
        urls = fetch_gdelt_urls(keywords, api_endpoint, time_window_hours, max_urls_per_run)
        
        assert len(urls) == 3  # Should get all URLs returned by API
        
        # Verify API was called with correct maxrecords parameter
        call_args = mock_requests.get.call_args
        assert call_args[1]["params"]["maxrecords"] == 5

    @patch('functions.gdelt_functions.requests')
    def test_fetch_gdelt_urls_request_failure(self, mock_requests):
        """Test GDelt URL fetching handles request failures"""
        from functions.gdelt_functions import fetch_gdelt_urls
        import requests
        
        # Mock request failure
        mock_requests.get.side_effect = requests.RequestException("API request failed")
        
        keywords = ["test"]
        api_endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"
        time_window_hours = 1
        max_urls_per_run = 100
        
        with pytest.raises(ValueError, match="GDelt API request failed"):
            fetch_gdelt_urls(keywords, api_endpoint, time_window_hours, max_urls_per_run)

    @patch('functions.gdelt_functions.requests')
    def test_fetch_gdelt_urls_invalid_json(self, mock_requests):
        """Test GDelt URL fetching handles invalid JSON response"""
        from functions.gdelt_functions import fetch_gdelt_urls
        
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_requests.get.return_value = mock_response
        
        keywords = ["test"]
        api_endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"
        time_window_hours = 1
        max_urls_per_run = 100
        
        with pytest.raises(ValueError, match="GDelt API response could not be parsed as JSON"):
            fetch_gdelt_urls(keywords, api_endpoint, time_window_hours, max_urls_per_run)

    @patch('airflow.operators.trigger_dagrun.TriggerDagRunOperator')
    def test_trigger_web_scraping_for_urls_success(self, mock_trigger_op_class):
        """Test successful URL injection"""
        from functions.gdelt_functions import trigger_web_scraping_for_urls
        
        # Mock context
        mock_context = {"dag_run": Mock(), "task_instance": Mock()}
        
        # Mock TriggerDagRunOperator
        mock_trigger_op = Mock()
        mock_trigger_op.execute.return_value = None
        mock_trigger_op_class.return_value = mock_trigger_op
        
        test_urls = [
            "https://example.com/article1",
            "https://example.com/article2",
            "https://example.com/article3"
        ]
        
        result = trigger_web_scraping_for_urls(test_urls, context=mock_context)
        
        # Verify results
        assert result["urls_found"] == 3
        assert result["url_list"] == test_urls
        assert result["urls_processed"] == 3
        assert result["triggered_count"] == 3
        assert result["failed_count"] == 0
        
        # Verify TriggerDagRunOperator was called for each URL
        assert mock_trigger_op_class.call_count == 3
        assert mock_trigger_op.execute.call_count == 3

    @patch('airflow.operators.trigger_dagrun.TriggerDagRunOperator')
    def test_trigger_web_scraping_for_urls_partial_failure(self, mock_trigger_op_class):
        """Test URL injection with partial failures"""
        from functions.gdelt_functions import trigger_web_scraping_for_urls
        
        # Mock context
        mock_context = {"dag_run": Mock(), "task_instance": Mock()}
        
        # Mock TriggerDagRunOperator with some failures
        def mock_trigger_side_effect(*args, **kwargs):
            mock_trigger_op = Mock()
            # Make the second URL fail
            if "article2" in str(kwargs.get("conf", {})):
                mock_trigger_op.execute.side_effect = Exception("Trigger failed")
            else:
                mock_trigger_op.execute.return_value = None
            return mock_trigger_op
        
        mock_trigger_op_class.side_effect = mock_trigger_side_effect
        
        test_urls = [
            "https://example.com/article1",
            "https://example.com/article2",  # This will fail
            "https://example.com/article3"
        ]
        
        result = trigger_web_scraping_for_urls(test_urls, context=mock_context)
        
        # Verify results
        assert result["urls_found"] == 3
        assert result["url_list"] == test_urls
        assert result["urls_processed"] == 3
        assert result["triggered_count"] == 2  # 2 successful
        assert result["failed_count"] == 1    # 1 failed

    @patch('airflow.operators.trigger_dagrun.TriggerDagRunOperator')
    def test_trigger_web_scraping_for_urls_empty_list(self, mock_trigger_op_class):
        """Test URL injection with empty URL list"""
        from functions.gdelt_functions import trigger_web_scraping_for_urls
        
        # Mock context
        mock_context = {"dag_run": Mock(), "task_instance": Mock()}
        
        test_urls = []
        
        result = trigger_web_scraping_for_urls(test_urls, context=mock_context)
        
        # Verify results
        assert result["urls_found"] == 0
        assert result["url_list"] == []
        assert result["urls_processed"] == 0
        assert result["triggered_count"] == 0
        assert result["failed_count"] == 0
        
        # Verify no triggers were attempted
        mock_trigger_op_class.assert_not_called()