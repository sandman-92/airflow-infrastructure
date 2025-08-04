# DAG Design Documentation

This document provides comprehensive design definitions for all DAGs in the Airflow infrastructure project. Each DAG definition includes a summary, input/output variables, task descriptions, and trigger mechanisms.

## Table of Contents

1. [Development Notes / Design Decisions](#development-notes--design-decisions)
2. [Web Scraping DAG](#web-scraping-dag)
3. [Create Embedding DAG](#create-embedding-dag)
4. [Database Migration DAG](#database-migration-dag)
5. [Example DAG](#example-dag)
6. [Example Called DAG](#example-called-dag)

---



## Development Notes / Design Decisions

1. I have configured XCOM to use a shared file system rather than the default database. this allows us to pass more data between tasks
2. For development, I am running two postgresql servers, as my model migration scripts were intefereing with the default apache airflow tables
3. I have edited the docker compose file to limit the resources in my development environment. For Production we will need to adjust the env variables
4. I have used default usernames and passwords, all databases and services will need better security


## Web Scraping DAG

### DAG Summary
**DAG ID:** `web_scraping_dag`  
**Description:** A comprehensive web scraping pipeline that extracts content from URLs, processes and stores the data as JSON files, and triggers embedding generation for the scraped content.  
**Schedule:** Every hour (`timedelta(hours=1)`)  
**Tags:** `['web-scraping', 'requests', 'beautifulsoup']`

### Input Variables
- **scraping_url** (Airflow Variable): Primary URL to scrape
- **url** (DAG configuration): URL to scrape (overrides Variable if provided)
- **retry_url** (DAG configuration): Boolean flag to retry failed URLs
- **rewrite_file** (DAG configuration): Boolean flag to overwrite existing JSON files

### Output Variables
- **scraped_data**: Raw HTML content and metadata from the scraped URL
- **json_result**: File path and database record information for the processed JSON
- **embedding_params**: Configuration parameters for the embedding DAG

### Tasks

#### 1. scrape_url
- **Inputs:** 
  - URL from Airflow Variable `scraping_url` or DAG config `url`
  - `retry_url_config` from DAG configuration
- **Outputs:** 
  - Scraped HTML content
  - URL metadata and status information
- **Function:** Scrapes web content using requests and BeautifulSoup, handles retries and error cases

#### 2. process_content
- **Inputs:** 
  - `scraped_data` from previous task (via XCom)
  - `rewrite_file` configuration flag
  - Processing metadata (DAG run ID, task ID, execution date)
- **Outputs:** 
  - JSON file path
  - Database record information
- **Function:** Processes scraped content and writes it to JSON files with metadata

#### 3. prepare_embedding_params
- **Inputs:** 
  - `json_result` from previous task (via XCom)
- **Outputs:** 
  - Dictionary with URL_ID, JSON_FILE_ID, text content, and model configuration
- **Function:** Prepares parameters needed for the embedding generation DAG

#### 4. trigger_embedding_dag
- **Inputs:** 
  - `embedding_params` from previous task (via XCom)
- **Outputs:** 
  - Trigger confirmation for create_embedding DAG
- **Function:** Triggers the create_embedding DAG with prepared parameters

### Task Dependencies
```
scrape_url >> process_content >> prepare_embedding_params >> trigger_embedding_dag
```

### What Can Trigger This DAG
- **Scheduled execution:** Runs automatically every hour
- **Manual trigger:** Can be triggered manually through Airflow UI
- **API trigger:** Can be triggered via Airflow REST API with optional configuration parameters

---

## Create Embedding DAG

### DAG Summary
**DAG ID:** `create_embedding`  
**Description:** Generates text embeddings using OpenAI's embedding models and stores them in Qdrant vector database with database tracking.  
**Schedule:** None (triggered manually or by other DAGs)  
**Tags:** `['embedding', 'qdrant', 'nlp', 'database']`

### Input Variables
- **URL_ID** (DAG configuration): Database ID of the URL record
- **JSON_FILE_ID** (DAG configuration): Database ID of the JSON file record
- **text** (DAG configuration): Text content to generate embeddings for
- **model** (DAG configuration): OpenAI embedding model (default: "text-embedding-3-small")
- **QdrantCollection** (DAG configuration): Qdrant collection name (default: "FullTextEmbedding")

### Output Variables
- **check_result**: Status of existing embedding check
- **embedding_result**: Generated embedding vector and metadata
- **storage_result**: Qdrant storage confirmation with point ID

### Tasks

#### 1. check_embedding_exists_task
- **Inputs:** 
  - `URL_ID` and `JSON_FILE_ID` from DAG configuration
- **Outputs:** 
  - Boolean indicating if embedding already exists
  - Existing embedding metadata if found
- **Function:** Checks database for existing embeddings to avoid duplicates

#### 2. generate_text_embedding_task
- **Inputs:** 
  - `check_result` from previous task (via XCom)
  - `text` content from DAG configuration
  - `model` specification from DAG configuration
- **Outputs:** 
  - Generated embedding vector
  - Embedding metadata and model information
- **Function:** Generates text embeddings using OpenAI API if not already exists

#### 3. store_embedding_in_qdrant_task
- **Inputs:** 
  - `URL_ID`, `JSON_FILE_ID`, `QdrantCollection` from DAG configuration
  - `embedding_result` from previous task (via XCom)
- **Outputs:** 
  - Qdrant point ID
  - Storage confirmation status
- **Function:** Stores embedding vectors in Qdrant and updates database records

### Task Dependencies
```
check_embedding_exists_task >> generate_text_embedding_task >> store_embedding_in_qdrant_task
```

### What Can Trigger This DAG
- **Manual trigger:** Through Airflow UI with required configuration parameters
- **Triggered by web_scraping_dag:** Automatically triggered after successful web scraping
- **API trigger:** Via Airflow REST API with configuration parameters

---

## Database Migration DAG

### DAG Summary
**DAG ID:** `database_migration_dag`  
**Description:** Handles database initialization, Alembic setup, and migration management for the project's data models.  
**Schedule:** None (manual trigger only)  
**Tags:** `['database', 'migration', 'alembic', 'initialization']`

### Input Variables
- No external input variables (uses internal database configuration)

### Output Variables
- **connection_status**: Database connection verification result
- **initialization_status**: Database initialization result
- **migration_status**: Current migration status and history

### Tasks

#### 1. check_database_connection_task
- **Inputs:** None (uses internal database configuration)
- **Outputs:** Database connection status and basic information
- **Function:** Verifies database connectivity and basic functionality

#### 2. initialize_database_task
- **Inputs:** None
- **Outputs:** Database initialization status
- **Function:** Creates database tables and initial schema if needed

#### 3. initialize_alembic (BashOperator)
- **Inputs:** None
- **Outputs:** Alembic initialization status
- **Function:** Initializes Alembic version control and stamps current schema as head

#### 4. generate_initial_migration (BashOperator)
- **Inputs:** None
- **Outputs:** Migration file generation status
- **Function:** Generates initial Alembic migration files based on current models

#### 5. run_migrations (BashOperator)
- **Inputs:** None
- **Outputs:** Migration execution status
- **Function:** Runs all pending Alembic migrations to update database schema

#### 6. check_migration_status_task
- **Inputs:** None
- **Outputs:** Current migration status and version information
- **Function:** Verifies final migration status and reports current database version

### Task Dependencies
```
check_database_connection_task >> initialize_database_task >> initialize_alembic >> generate_initial_migration >> run_migrations >> check_migration_status_task
```

### What Can Trigger This DAG
- **Manual trigger:** Through Airflow UI for database setup and maintenance
- **API trigger:** Via Airflow REST API for automated deployment scenarios

---

## DAG Interaction Flow

The DAGs in this project form an interconnected workflow:

1. **gdelt_url_injestion_dag** → **web_scraping_dag**: GDelt URL injection feeds URLs to web scraping
2. **web_scraping_dag** → **create_embedding_dag**: Web scraping triggers embedding generation
3. **example_dag** → **example_called_dag**: Demonstration of DAG-to-DAG triggering
4. **database_migration_dag**: Standalone DAG for database management

## Common Configuration Patterns

### Retry Configuration
All DAGs use consistent retry patterns:
- **Retries:** 1 attempt
- **Retry Delay:** 5 minutes (2 minutes for example_dag)

### Scheduling Patterns
- **Scheduled:** gdelt_url_injestion_dag (every 10 minutes), web_scraping_dag (hourly)
- **On-demand:** create_embedding_dag, database_migration_dag
- **Manual/Demo:** example_dag, example_called_dag

### Database Integration
- **gdelt_url_injestion_dag:** Creates URLInjestion records with "Queued" status for discovered URLs
- **web_scraping_dag:** Creates and updates URL and JSON file records
- **create_embedding_dag:** Creates and updates embedding records
- **database_migration_dag:** Manages database schema and migrations


## GDelt URL Injestion DAG

### DAG Summary
**DAG ID:** `gdelt_url_injestion_dag`  
**Description:** Queries the GDelt library on a scheduled basis to fetch URLs related to specific keywords and injects them into the the web scraping DAG to process.  
**Schedule:** `*/10 * * * *` (every 10 minutes)  
**Tags:** `['gdelt', 'url-injestion', 'news', 'scheduled']`

### Input Variables
- **keywords**: List of keywords to search for in GDelt data (configurable via Airflow Variables)
- **gdelt_api_endpoint**: GDelt API endpoint URL (configurable via Airflow Variables)
- **max_urls_per_run**: Maximum number of URLs to inject per DAG run (default: 100)
- **time_window_hours**: Time window in hours to look back for GDelt data (default: 1)

### Output Variables
- **urls_found**: Number of URLs discovered from GDelt API
- **url_list**: list of URLS

### Tasks

#### 1. validate_configuration_task
- **Inputs:** None (reads from Airflow Variables)
- **Outputs:** 
  - Validated configuration parameters
  - Keywords list and API endpoint verification
- **Function:** Validates that required Airflow Variables are set and accessible, ensures keywords list is not empty

#### 2. fetch_gdelt_data_task
- **Inputs:** 
  - `keywords` from configuration
  - `gdelt_api_endpoint` from configuration
  - `time_window_hours` from configuration
- **Outputs:** 
  - list of URLs
- **Function:** Queries GDelt API for articles matching specified keywords within the time window


#### 4. inject_urls_task
- **Inputs:** 
  - `extracted_urls` from previous task (via XCom)
  - URL metadata from extract_urls_task
- for every URL trigger the web scraping dag


### Task Dependencies
```
validate_configuration_task >> fetch_gdelt_data_task >>  inject_urls_task 
```

### What Can Trigger This DAG
- **Scheduled trigger:** Runs automatically every 10 minutes via cron schedule
- **Manual trigger:** Through Airflow UI for testing or manual URL injection


---

