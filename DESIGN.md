# DAG Design Documentation


## GDELT URL Ingestion DAG

### Overview
The `gdelt_url_injestion_dag` is an Airflow-managed data ingestion pipeline that fetches news article URLs from the GDELT (Global Database of Events, Language, and Tone) API based on configurable keywords and time windows. It serves as a fanout orchestrator that triggers the `web_scraping_dag` for each discovered URL, enabling automated discovery and processing of news content for downstream analysis.

The DAG operates as a scheduled or manually triggered workflow that queries GDELT's real-time news feed, filters articles by keywords and language, and optionally persists URL batches for audit trails before triggering individual scraping jobs.

---

### Objectives
- Automate discovery of relevant news articles from GDELT's global news database.
- Support keyword-based filtering with configurable time windows for recent content.
- Enable fanout processing by triggering individual web scraping jobs for each discovered URL.
- Provide optional batch persistence for audit trails and reprocessing capabilities.
- Maintain flexible configuration through Airflow Variables and DAG run parameters.
- Ensure robust error handling and logging for API interactions.

---

### Data Flow
1. **Validate Configuration**  
   - Reads configuration from Airflow Variables and DAG run parameters.
   - Validates required parameters:
     - `gdelt_keywords` (list of search terms)
     - `gdelt_api_endpoint` (GDELT API URL)
     - `gdelt_max_urls_per_run` (default: 100)
     - `gdelt_time_window_hours` (default: 1)
   - Merges runtime overrides from `dag_run.conf`:
     - `trigger_scrapers` (default: True)
     - `write_batch_json` (default: False)

2. **Fetch URLs from GDELT**  
   - Queries GDELT API for each configured keyword.
   - Constructs time-bounded queries using `startdatetime` parameter.
   - Filters for English-language articles only.
   - Sorts results by date (most recent first).
   - Aggregates URLs from all keyword searches.
   - Enriches each URL record with the originating keyword.

3. **Write Batch JSON (Optional)**  
   - If `write_batch_json` is enabled, persists all discovered URLs to disk.
   - Creates timestamped batch files in `/opt/airflow/data/url_batches/`.
   - Stores complete article metadata for audit and reprocessing.

4. **Prepare URLs for Triggering**  
   - Filters URLs based on `trigger_web_scraper` configuration.
   - Returns empty list if triggering is disabled, allowing batch-only runs.

5. **Fan-out Trigger Web Scrapers**  
   - Uses `TriggerDagRunOperator` with dynamic task mapping.
   - Generates unique run IDs using URL hash and timestamp.
   - Triggers `web_scraping_dag` for each URL with complete article metadata.
   - Operates asynchronously without waiting for completion.

---

### Key Design Considerations
- **Fanout Architecture:**  
  Designed as an orchestrator DAG that discovers URLs and delegates processing to specialized scraping workflows.
  
- **Configurable Discovery:**  
  Supports multiple keywords and adjustable time windows for flexible content discovery strategies.
  
- **Error Isolation:**  
  API failures for individual keywords don't prevent processing of other keywords.
  
- **Audit Trail:**  
  Optional batch JSON persistence enables reprocessing and debugging of discovery runs.
  
- **Resource Management:**  
  Configurable limits on URLs per run prevent overwhelming downstream systems.
  
- **Integration Points:**  
  - **GDELT API:** Real-time global news database for content discovery.  
  - **Web Scraping DAG:** Downstream processing pipeline for individual URLs.  
  - **File System:** Batch persistence for audit trails and reprocessing.

---

### Configuration Parameters
| Variable Name               | Purpose                                          | Default        |
|-----------------------------|--------------------------------------------------|----------------|
| `gdelt_keywords`            | List of search terms for GDELT API queries      | Required       |
| `gdelt_api_endpoint`        | GDELT API endpoint URL                           | Required       |
| `gdelt_max_urls_per_run`    | Maximum URLs to fetch per keyword per run       | `100`          |
| `gdelt_time_window_hours`   | Hours back from current time to search          | `1`            |
| `trigger_scrapers`          | Enable triggering of web scraping DAGs          | `True`         |
| `write_batch_json`          | Enable batch JSON file persistence              | `False`        |

---


## Web Scraping and Embedding Pipeline DAG

### Overview
The `web_scraping_dag` is an Airflow-managed ETL pipeline that ingests a URL, scrapes its HTML content, stores the raw and processed data, and generates a semantic vector embedding for search and retrieval.

The DAG ensures that each stage of the workflow runs only when necessary, preventing redundant scraping, file writes, or embedding generation. It integrates with a relational database (SQLAlchemy models), file storage for scraped JSON, and a Qdrant vector database for embedding storage.

---

### Objectives
- Automate ingestion and processing of new URLs for downstream vector search.
- Maintain idempotent operations — avoid re-scraping or re-embedding unless explicitly overridden.
- Support dynamic triggering via Airflow’s `dag_run.conf` parameters.
- Store intermediate artifacts (JSON) for auditability and reprocessing.
- Ensure robust error handling and logging at each stage.

---

### Data Flow
1. **Validate Inputs**  
   - Reads DAG run configuration from `dag_run.conf`.  
   - Merges runtime overrides from Airflow Variables:
     - `scrape_url_override`
     - `url_meta_data_override`
     - `json_write_override`
     - `trigger_embeddings_override`
     - `collection` (default: `test_urls`)

2. **Check Should Scrape**  
   - Looks up the URL in the `URL` table.  
   - If new, inserts and marks for scraping.  
   - If existing, only triggers scrape if `json_file_path` is missing.

3. **Scrape URL**  
   - Uses `requests` with retry/backoff and a custom User-Agent.  
   - Parses HTML with BeautifulSoup, removes non-content elements, and cleans text.  
   - Skips short (<1000 chars) pages via `AirflowSkipException`.  
   - Stores `scraped_text` and `scraped_title` in the config.

4. **Should Write JSON**  
   - Computes a deterministic JSON file path by hashing the URL.  
   - Updates `URL.json_file_path` in the DB if not already set.  
   - Marks whether to write the JSON file in this run.

5. **Write JSON**  
   - Persists scraped title and text to disk as JSON.  
   - Updates the `json_file_path` in the DB.

6. **Should Trigger Embeddings**  
   - Checks if an embedding for the URL already exists in the `Embedding` table.  
   - If not, inserts a placeholder to avoid race conditions.  
   - Propagates the `collection` name for Qdrant storage.

7. **Fetch Embedding & Save to Qdrant**  
   - Generates an embedding via the OpenAI API (model: `text-embedding-3-small` by default).  
   - Ensures the Qdrant collection exists, creating it if needed.  
   - Upserts the embedding vector into Qdrant with URL metadata.  
   - Inserts an `Embedding` DB row linking the URL to its Qdrant index.

---

### Key Design Considerations
- **Idempotency:**  
  Each stage checks DB state before proceeding to prevent duplicate work.
  
- **Error Handling:**  
  Failures in scraping or embedding stop dependent stages (`TriggerJson` / `TriggerEmbedding` flags).  
  Uses `AirflowSkipException` for expected skips (e.g., insufficient content).
  
- **Extensibility:**  
  Modular @task-decorated functions allow inserting alternative scrapers or embedding models without DAG refactor.
  
- **Persistence & Reprocessing:**  
  JSON artifacts are hashed by URL for deterministic storage paths, enabling later reload without re-scraping.
  
- **Integration Points:**  
  - **Database:** URL and embedding metadata stored in SQLAlchemy models.  
  - **Vector Store:** Embeddings stored in Qdrant with cosine distance metric.  
  - **OpenAI API:** Generates semantic embeddings from scraped text.

---

### Configuration Parameters
| Variable Name               | Purpose                                          | Default        |
|-----------------------------|--------------------------------------------------|----------------|
| `scrape_url_override`       | Force scraping even if JSON exists                | `False`        |
| `url_meta_data_override`    | Force URL metadata processing                     | `False`        |
| `json_write_override`       | Force JSON writing even if file exists            | `False`        |
| `trigger_embeddings_override`| Force embedding generation even if exists         | `False`        |
| `collection`                | Qdrant collection name for embeddings             | `test_urls`    |


---





