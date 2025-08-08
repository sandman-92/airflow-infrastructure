# Apache Airflow Infrastructure with Auth0 Authentication

This repository contains a Docker Compose setup for deploying Apache Airflow with Auth0 authentication, alongside Redis, PostgreSQL, and Qdrant vector database services.

## Quick Start

### Clone Project

clone project and change directory to repo
```bash
git clone && cd airflow-infrastructure
```
read through the airflow compose quickstart [link](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html)
fill in the environment file

```dotenv

# Replace this with your userID
AIRFLOW_UID=1000
# Apache Airflow Configuration
AIRFLOW_IMAGE_NAME=apache/airflow:3.0.3
#AIRFLOW_UID=50000
AIRFLOW_PROJ_DIR=.

# Default Airflow Admin User (used for initial setup)
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow

## Auth0 Configuration
## Replace these values with your Auth0 application settings
#AUTH0_DOMAIN=https://your-domain.auth0.com
#AUTH0_CLIENT_ID=your-auth0-client-id
#AUTH0_CLIENT_SECRET=your-auth0-client-secret

# Additional Python Requirements (optional)
# Add any additional Python packages you need
_PIP_ADDITIONAL_REQUIREMENTS=authlib flask-oidc requests beautifulsoup4 alembic sqlalchemy psycopg2-binary qdrant-client numpy pandas openai apache-airflow[statsd] apache-airflow[sentry]

AIRFLOW__CORE__LOAD_EXAMPLES=False
AIRFLOW__LOGGING__LOGGING_LEVEL=INFO

#This allows tasks to communicate via the file system. Important for scheduling 1000+ tasks
AIRFLOW__CORE__XCOM_BACKEND=airflow.providers.common.io.xcom.backend.XComObjectStorageBackend
AIRFLOW__COMMON_IO__XCOM_OBJECTSTORAGE_PATH=file:///opt/airflow/data/xcoms
# Airflow Concurrency and Parallelism Configuration

# Maximum number of task instances that can run simultaneously across the entire Airflow instance
AIRFLOW__CORE__PARALLELISM=16
# Maximum number of tasks that can run concurrently within a single DAG
AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=8
# Number of tasks a single Celery worker can execute simultaneously
AIRFLOW__CELERY__WORKER_CONCURRENCY=16
# Maximum number of DAG runs that can be active at the same time for each DAG
AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=2

# Resource Allocation Configuration
# tune this so it fits into your system

# Airflow postgres server
POSTGRES_CPU_ALLOCATION=1
POSTGRES_RAM_ALLOCATION=2G

# App Postgres server
POSTGRES_APP_CPU_ALLOCATION=1
POSTGRES_APP_RAM_ALLOCATION=2G

# Redis server
REDIS_CPU_ALLOCATION=0.25
REDIS_RAM_ALLOCATION=512M

# Qdrant vector database
QDRANT_CPU_ALLOCATION=0.5
QDRANT_RAM_ALLOCATION=1G

# Airflow API server
AIRFLOW_APISERVER_CPU_ALLOCATION=2.0
AIRFLOW_APISERVER_RAM_ALLOCATION=8G

# Airflow scheduler
AIRFLOW_SCHEDULER_CPU_ALLOCATION=1.0
AIRFLOW_SCHEDULER_RAM_ALLOCATION=2G

# Airflow DAG processor
AIRFLOW_DAG_PROCESSOR_CPU_ALLOCATION=1
AIRFLOW_DAG_PROCESSOR_RAM_ALLOCATION=8G

# Airflow worker
AIRFLOW_WORKER_CPU_ALLOCATION=4
AIRFLOW_WORKER_RAM_ALLOCATION=16G

# Airflow triggerer
AIRFLOW_TRIGGERER_CPU_ALLOCATION=0.5
AIRFLOW_TRIGGERER_RAM_ALLOCATION=1G

# Flower monitoring
FLOWER_CPU_ALLOCATION=0.25
FLOWER_RAM_ALLOCATION=1G

OPENAI_API_KEY=
```
run 
```bash
docker compose up airflow-init
docker compose up -d --build --force-recreate
```

initialize our project database
1. go to https://localhost:8080
2. navigate to dags
3. trigger the database_migration_dag (this initializes our database with our model.py file)

docker exec into the api server and run the command 
```bash
airflow variables import dag/variables.json
```
this imports our workflow variables from the json file 

## Services Included

- **Apache Airflow 3.0.3**: Complete Airflow deployment with CeleryExecutor
  - API Server (Web UI): `http://localhost:8080`
  - Scheduler: Background task scheduling
  - Worker: Task execution
  - Triggerer: Handles deferred tasks
  - DAG Processor: Processes DAG files
- **PostgreSQL 13**: Primary database for Airflow metadata
- **Redis 7.2**: Message broker for Celery executor
- **Qdrant**: Vector database for AI/ML workloads
  - HTTP API: `http://localhost:6333`
  - gRPC API: `http://localhost:6334`

## Prerequisites

- Docker and Docker Compose installed