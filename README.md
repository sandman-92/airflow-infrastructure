# Apache Airflow Infrastructure with Auth0 Authentication

This repository contains a Docker Compose setup for deploying Apache Airflow with Auth0 authentication, alongside Redis, PostgreSQL, and Qdrant vector database services.

## Quick Start

### Clone Project

clone project and change directory to repo
```bash
git clone && cd airflow-infrastructure
```
fill in environment file
```dotenv
AIRFLOW_UID=YOUR UID
# Apache Airflow Configuration
AIRFLOW_IMAGE_NAME=apache/airflow:3.0.3
#AIRFLOW_UID=50000
AIRFLOW_PROJ_DIR=.

# Default Airflow Admin User (used for initial setup)
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow

# Auth0 Configuration
# Replace these values with your Auth0 application settings
AUTH0_DOMAIN=https://your-domain.auth0.com
AUTH0_CLIENT_ID=your-auth0-client-id
AUTH0_CLIENT_SECRET=your-auth0-client-secret

# Additional Python Requirements (optional)
# Add any additional Python packages you need
_PIP_ADDITIONAL_REQUIREMENTS=authlib flask-oidc requests beautifulsoup4 alembic sqlalchemy psycopg2-binary qdrant-client numpy pandas openai

AIRFLOW__CORE__LOAD_EXAMPLES=False

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
airflow variables load dag/variables.json
```
this loads our workflow variables from the json file 

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
- Auth0 account and application configured
- At least 4GB RAM and 2 CPU cores recommended
- 10GB+ free disk space

### 2. Configure Environment Variables

Copy the template and configure your settings:

```bash
cp .env.template .env
```

Edit the `.env` file with your Auth0 credentials:

```bash
# Auth0 Configuration
AUTH0_DOMAIN=https://your-domain.auth0.com
AUTH0_CLIENT_ID=your-auth0-client-id
AUTH0_CLIENT_SECRET=your-auth0-client-secret
```

### 3. Auth0 Application Setup

1. **Create Auth0 Application**:
   - Go to Auth0 Dashboard → Applications
   - Create a new "Regular Web Application"
   - Note the Domain, Client ID, and Client Secret

2. **Configure Callback URLs**:
   - Allowed Callback URLs: `http://localhost:8080/oauth-authorized/auth0`
   - Allowed Logout URLs: `http://localhost:8080/logout`
   - Allowed Web Origins: `http://localhost:8080`

3. **Configure Application Settings**:
   - Enable "OIDC Conformant" in Advanced Settings
   - Set Grant Types: Authorization Code, Refresh Token

### 4. Initialize and Start Services

```bash
# Create required directories
mkdir -p ./dags ./logs ./plugins ./config

# Set proper permissions (Linux/macOS)
echo -e "AIRFLOW_UID=$(id -u)" >> .env

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### 5. Access Services

- **Airflow Web UI**: http://localhost:8080
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Flower (Celery Monitor)**: http://localhost:5555 (optional, use `--profile flower`)

## Auth0 Authentication Flow

1. Navigate to http://localhost:8080
2. Click "Sign in with auth0"
3. Complete Auth0 authentication
4. You'll be redirected back to Airflow with proper permissions

## Configuration Details

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH0_DOMAIN` | Your Auth0 domain | Required |
| `AUTH0_CLIENT_ID` | Auth0 application client ID | Required |
| `AUTH0_CLIENT_SECRET` | Auth0 application client secret | Required |
| `AIRFLOW_UID` | User ID for Airflow containers | 50000 |
| `_AIRFLOW_WWW_USER_USERNAME` | Initial admin username | airflow |
| `_AIRFLOW_WWW_USER_PASSWORD` | Initial admin password | airflow |

### Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Airflow Web UI | 8080 | Main web interface |
| Qdrant HTTP | 6333 | Vector database HTTP API |
| Qdrant gRPC | 6334 | Vector database gRPC API |
| Flower | 5555 | Celery monitoring (optional) |

### Volumes

- `postgres-db-volume`: PostgreSQL data persistence
- `qdrant-storage`: Qdrant vector database storage
- `./dags`: Airflow DAG files
- `./logs`: Airflow logs
- `./plugins`: Airflow plugins
- `./config`: Airflow configuration files

## Development Workflow

### Adding DAGs

1. Place your DAG files in the `./dags` directory
2. They will be automatically picked up by Airflow
3. Refresh the web UI to see new DAGs

### Custom Configuration

1. Create custom `airflow.cfg` in `./config` directory
2. Restart services: `docker-compose restart`

### Scaling Workers

```bash
# Scale Celery workers
docker-compose up -d --scale airflow-worker=3
```

## Troubleshooting

### Common Issues

1. **Permission Errors**:
   ```bash
   # Fix ownership issues
   sudo chown -R $(id -u):$(id -g) ./dags ./logs ./plugins ./config
   ```

2. **Auth0 Login Issues**:
   - Verify callback URLs in Auth0 dashboard
   - Check Auth0 domain format (include https://)
   - Ensure client credentials are correct

3. **Service Health Checks**:
   ```bash
   # Check service logs
   docker-compose logs airflow-webserver
   docker-compose logs postgres
   docker-compose logs redis
   docker-compose logs qdrant
   ```

4. **Database Connection Issues**:
   ```bash
   # Reinitialize database
   docker-compose down -v
   docker-compose up -d
   ```

### Validation

```bash
# Validate docker-compose syntax
docker-compose config

# Check service health
docker-compose ps
```

## Security Considerations

- Change default passwords in production
- Use strong Auth0 client secrets
- Configure proper Auth0 rules and roles
- Enable HTTPS in production deployments
- Regularly update container images

## Production Deployment

For production use:

1. Use external databases instead of containers
2. Configure proper secrets management
3. Set up SSL/TLS certificates
4. Configure proper logging and monitoring
5. Use container orchestration (Kubernetes)
6. Set up backup strategies for data volumes

## Support

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Auth0 Documentation](https://auth0.com/docs)
- [Qdrant Documentation](https://qdrant.tech/documentation/)

## License

This project follows the Apache License 2.0, same as Apache Airflow.