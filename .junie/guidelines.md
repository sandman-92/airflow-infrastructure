# 📘 Project Guidelines for Junie

This document outlines the coding standards, testing strategy, and development environment setup for contributing to this project, which is built around **Apache Airflow**, **Google Cloud Build**, and developed in **Windows Subsystem for Linux (WSL)**.

---

## 🔢 Versions and Compatibility

- Python: 3.12.x (pin exact minor in `pyproject.toml`)
- Poetry: 2.0.2
- Apache Airflow: 3.x (ensure all examples/tests use Airflow 3 APIs)
- Providers: Pin versions in `pyproject.toml` to avoid drift
- Docker Compose: v2 (`docker compose ...`)

Document changes in a CHANGELOG and update these pins when upgrading.

---

## 🖥 Operating System

- Development is done inside **Windows Subsystem for Linux (WSL)** (Ubuntu recommended).
- Use **Linux commands** and **Linux file paths** at all times.
- Project base directory: /home/<user>/GitHub/airflow-infrastructure
- Docker Compose commands use v2 syntax: `docker compose`

Notes:
- Ensure Docker Desktop uses the WSL 2 backend.
- Keep the project inside the Linux filesystem (not mounted Windows paths) for performance.

---

## 🚀 Quickstart

1. Install prerequisites: WSL distro, Docker Desktop (WSL backend), Python 3.12, Poetry 2.0.2
2. Clone repo into WSL filesystem.
3. Install dependencies:
   ```bash
   poetry install
   ```
4. Set environment (copy and edit sample):
   ```bash
   cp .env.sample .env
   ```
5. Start local stack:
   ```bash
   docker compose up -d
   ```
6. Run checks:
   ```bash
   poetry run black dags/ dag_tests/
   poetry run isort dags/ dag_tests/ --profile black
   poetry run flake8 dags/ dag_tests/
   poetry run pytest -q
   ```

---

## 🧠 Project Scope

Junie must be proficient in:

- **Apache Airflow** (DAG authoring, orchestration, best practices)
- **Google Cloud Build** for CI/CD
- **Python development** in **WSL** with **Poetry 2.0.2** and virtual environments

---

## 📁 Project Structure

project-root/
├── dags/                  # Main DAG files
    ├── gpt_prompts/       # Module for GPT prompts
├── dag_tests/             # DAG unit tests
├── config/                # Apache Airflow config folder
├── cloudbuild/            # Cloud Build configuration directory
├── notebooks/             # Non-essential Jupyter notebooks
├── pyproject.toml         # Poetry environment setup
├── docker-compose.yaml    # Docker Compose for development
├── .env.sample            # Document required env vars (no secrets)
└── junie/.guidelines.md   # This file

---

## 🐍 Python & Poetry

- Python development is done inside **WSL**.
- Poetry manages the virtual environment.
- Activate (Poetry 2.0.2):
  ```bash
  poetry env activate
  ```
  Then run the returned `source /path/to/venv/bin/activate`.
- One-off commands:
  ```bash
  poetry run <command>
  ```

---

## 🔐 Configuration & Secrets

- Never commit secrets. Use placeholders like <PROJECT_ID>, <REGION>, etc.
- Local development:
  - Store non-sensitive config in `.env` (based on `.env.sample`).
  - Mount environment variables via `docker-compose.yaml`.
- CI/CD and production:
  - Store secrets in Secret Manager or CI secret store.
  - Inject at runtime; do not write secrets to images or logs.

---

## 🎯 DAG Coding Standards

### Style & Linting

- PEP8, black, isort (profile=black), flake8
- Prefer type hints for helpers and tasks
- Avoid import-time side effects (no network, file writes, or heavy compute)

### Structure

1. Imports order: Stdlib → Third-party → Airflow → Local
2. DAG definition:
   ```python
   with DAG(...) as dag:
       ...
   ```
3. Helper functions at bottom or imported from helper modules
4. Context extraction only inside `@task` functions
5. Dates: Use `pendulum` with tz-aware datetimes (no `datetime.utcnow()`)
6. Naming:
   - DAG IDs: `<domain>__<name>__v<major>`
   - Task IDs: verbs with clear intent, lowercase with underscores
   - Tags: include team, domain, environment

### Runtime Practices

- Idempotent tasks; safe retries and backoff
- Configure SLAs/alerts where appropriate
- Use pools/queues for resource control
- Prefer datasets/deferrable operators when applicable
- XCom: keep payloads small; use external storage for large data

---

## ✅ Details to Check

1. XCom pulls reference existing tasks; handle lists from mapped tasks
2. Task mapping fan-out sizes are bounded; concurrency/pools configured
3. `catchup`, `max_active_runs`, `schedule`/`schedule_interval` defined explicitly
4. DAG and tasks include `doc_md`, tags, and owner metadata

---

## 🧪 Testing Strategy

For every DAG in `dags/`, create a corresponding test in `dag_tests/`.

### Levels

- Unit tests: helpers and small task logic (mock I/O)
- DAG import tests: `DagBag` import, task count, dependencies, policy conformance
- Optional integration smoke: run a minimal DAG locally in Docker

### Conventions

- File mapping: `dags/my_dag.py` → `dag_tests/test_my_dag.py`
- Runner:
  ```bash
  poetry run pytest
  ```
- Consider parametric policy tests enforcing:
  - Naming rules, required tags
  - `catchup=False`, `max_active_runs=1`
  - Start date timezone awareness

---

## 🧰 Pre-commit (Optional but Recommended)

Install hooks to enforce formatting and basic DAG checks pre-push: