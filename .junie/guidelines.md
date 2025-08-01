# 📘 Project Guidelines for Junie

This document outlines the coding standards, testing strategy, and development environment setup for contributing to this project, which is built around Apache Airflow, Google Cloud Build, and developed in **Windows Subsystem for Linux (WSL)**.

## Operating System

* project is being developed in windows subsystem linux. use linux commands and linux file paths. 
* the project base directory is in /home/sandy/GitHub/airflow-infrastructure

## 🧠 Project Scope

Junie is expected to be proficient in:

* **Apache Airflow** (DAG authoring and orchestration)
* **Google Cloud Build**
* **Python Development** in **WSL with Poetry and virtual environments**

---

## 📁 Project Structure

```
project-root/
├── dags/                  # Main DAG files
├── test_dags/             # DAG unit tests
├── cloudbuild/            # Cloud Build configuration directory
├── pyproject.toml         # Poetry environment setup
└── junie/.guidelines.md         # This file
```

---

## 🐍 Python Environment

* Python development is done inside **WSL**.
* A **Poetry-managed virtual environment** is used.
* Ensure the virtual environment is activated before working:

  ```bash
  poetry env activate 
  ```

---

## 🎯 DAG Coding Standards

### ✅ Code Style

* Use **PEP8-compliant** code.
* Code must pass:

  * `black`
  * `flake8`
  * `isort`

### ✅ Structure

1. **Imports:** Standard Python → Third-party → Airflow → Local
2. **Function Definitions:** Top of the file, above the DAG context.
3. **DAG Definition:** Should be wrapped in a `with DAG(...) as dag:` block.
4. **Context extraction** like `get_current_context()` must be placed inside `@task`-decorated functions.

### ✅ Example Template

Every new DAG file should follow this pattern:

```python
from airflow import DAG
from airflow.decorators import task
from airflow.operators.python import get_current_context
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta


def example_function(*args, **kwargs):
    """
    Example function to demonstrate reusable logic.

    :return: str
    """
    return "Call this function"


default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    dag_id='example_dag',
    default_args=default_args,
    start_date=datetime.utcnow() - timedelta(days=1),
    schedule=None,
    catchup=False,
    tags=['airflow-3.0', 'example', 'fanout-fanin'],
) as dag:

    @task()
    def task_1():
        example_function()
        return "initial payload"

    @task()
    def task_2(previous):
        return ["alpha", "beta", "gamma"]

    @task()
    def task_3(item: str):
        return f"processed_{item}"

    @task()
    def task_4():
        context = get_current_context()
        ti = context["ti"]
        results = ti.xcom_pull(task_ids="task_3")
        for result in results:
            print(f"Result: {result}")
        return results

    trigger_called_dag = TriggerDagRunOperator(
        task_id='trigger_called_dag',
        trigger_dag_id='example_called_dag',
        wait_for_completion=False,
    )

    t1 = task_1()
    t2 = task_2(t1)
    t3_mapped = task_3.expand(item=t2)
    t4_task = task_4()

    t3_mapped >> t4_task >> trigger_called_dag
```

---

## 🧪 Testing Strategy

For **every DAG file** in `dags/`, there must be a corresponding test file in `test_dags/`:

### ✅ Naming Convention

For `dags/my_dag.py`, create:
`test_dags/test_my_dag.py`

### ✅ Test Runner

Use `pytest` inside the Poetry shell:

```bash
poetry run pytest
```

### ✅ Minimum Test Coverage

Each DAG test must:

* Load the DAG successfully.
* Assert the correct number of tasks.
* Assert the expected dependencies using `dag.get_task(...)`.
* Optionally: test logic in any helper functions defined at the top.

### ✅ Example Test Template

```python
import pytest
from airflow.models import DagBag

@pytest.fixture
def dagbag():
    return DagBag(dag_folder="dags", include_examples=False)

def test_dag_loaded(dagbag):
    dag = dagbag.get_dag(dag_id="example_dag")
    assert dag is not None
    assert len(dag.tasks) == 4  # Adjust based on your DAG structure
```

---

## 🚩 Linting & Formatting

To ensure all code meets standards, run the following in the root directory:

```bash
poetry run black dags/ test_dags/
poetry run isort dags/ test_dags/
poetry run flake8 dags/ test_dags/
```

Automate this via a `pre-commit` hook or CI/CD step in Cloud Build.

---

## 🚀 Cloud Build

* Your `cloudbuild.yaml` must include test + lint steps.
* Optionally: run DAG validation in CI by importing and asserting DAG parsing.

---

## 📝 Summary Checklist

Before submitting a DAG:

* [ ] DAG follows structural and stylistic standards
* [ ] `test_*.py` exists in `test_dags/` for every DAG
* [ ] Code passes `black`, `flake8`, and `isort`
* [ ] All tests pass via `pytest`
* [ ] Developed and tested within WSL environment using Poetry
