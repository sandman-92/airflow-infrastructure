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
│   └── functions/         # Reusable functions for DAGs (separated from DAG definitions)
├── dag_tests/             # DAG unit tests
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

1. **Imports:** Standard Python → Third-party → Airflow → Local (including functions modules)
2. **Function Organization:** Reusable functions should be placed in `dags/functions/` modules, separated from DAG definitions to avoid import issues during testing.
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

# Import functions from functions module
from functions.example_functions import example_function


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

### Details to check

1. when passing variables between tasks, ensure the ti.xcom_pull(task_ids="task_id") call and variable points to the correct task. 
2. if a ti.xcom_pull(task_ids="non_existant_task") points to a task that doesnt exist please flag this. 

---

## 🧪 Testing Strategy

For **every DAG file** in `dags/`, there must be a corresponding test file in `dag_tests/`:

### ✅ Naming Convention

For `dags/my_dag.py`, create:
`dag_tests/test_my_dag.py`

### ✅ Test Runner

Use `pytest` inside the Poetry shell:

```bash
poetry run pytest
```

### ✅ Minimum Test Coverage

Tests must include both function-level tests and DAG-level tests.

#### Function Tests

Each function test must:
* Assert that the function runs correctly when given valid inputs.

* Provide test cases that exercise every logical branch in the function (e.g. all if / else conditions).

* Verify that the function raises appropriate and meaningful errors when given invalid or unexpected inputs.

#### DAG Tests

Each DAG test must:

* Successfully load the DAG from the dags/ directory.
* Assert that the correct number of tasks are defined.
* Validate task dependencies using dag.get_task(...) and .downstream_task_ids.
* Test reusable functions from the functions modules separately.

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

## DAG Development Workflow

Follow this workflow when developing dags or significant changes:
1. Consult the DESIGN.md file
   - If implementing a new feature or making a major change, check for an existing design entry.
   - If not present, add a detailed design entry describing the intent, scope, and rationale before coding.
2. Write a test for the planned feature
   - Define the expected behavior of the feature. either by creating or modifying the relevent file in the dag_tests directory
   - Cover normal cases, edge cases, and failure modes.
   - Tests must be meaningful and aligned with the Minimum Test Coverage rules.
3. Write the implementation code
   - Focus only on what’s needed to pass the test.
   - Keep the code concise, clear, and consistent with the style guidelines.
4. Run the full test suite
   - Run the new test and all existing tests using:
   ```bash
   poetry run pytest
   ```
Optional but encouraged: Commit changes in logical units (design, test, implementation, etc.) to keep the history clean.

## 🚩 Linting & Formatting

To ensure all code meets standards, run the following in the root directory:

```bash
poetry run black dags/ dag_tests/
poetry run isort dags/ dag_tests/
poetry run flake8 dags/ dag_tests/
```

Automate this via a `pre-commit` hook or CI/CD step in Cloud Build.

---

## 🚀 Cloud Build

* Your `cloudbuild.yaml` must include test + lint steps.
* Optionally: run DAG validation in CI by importing and asserting DAG parsing.

---

## Non-Hallucination Coding Instructions

To ensure high-quality, relevant, and maintainable code, follow these rules:

* Do not hallucinate functionality. Only write code or tests for logic that actually exists in the codebase.
* Do not include placeholder or TODO comments. All code must be complete and production-ready. 
  * Where code is incomplete, include in a {TASK SUMMARY}.md file as a future improvement
* Do not create artificial or informational code blocks that are not directly tested. For example, avoid defining lists or printing summaries that serve no functional purpose unless they are directly involved in a test case.
  Avoid this:
```python
def test_migration_summary():
    migrated_functions = ["a", "b", "c"]
    assert len(migrated_functions) == 3
```
* Only include information in code if it is directly used to test real behavior. Any constants, data structures, or branches in tests must exercise or validate real application logic.
* Avoid metadata-only or self-validating tests. Tests should verify real execution paths, outcomes, and edge cases—not static properties or documentation.
* Write only meaningful assertions. Avoid asserting hardcoded lengths, counts, or logs unless they are necessary to validate task outputs or errors.
* Focus test coverage on real DAG behavior and task logic.
  * Ensure DAGs can be parsed and loaded.
  * Validate task relationships and data flow.
  * Test @task-decorated functions if they contain logic or branching.
* Keep code clean and readable, but:
  * Avoid unnecessary abstraction or boilerplate.
  * Do not add unused helpers, comments, or documentation unless it adds clear value.


## 📝 Summary Checklist

Before submitting a DAG:

* [ ] DAG follows structural and stylistic standards
* [ ] `test_*.py` exists in `dag_tests/` for every DAG
* [ ] Code passes `black`, `flake8`, and `isort`
* [ ] All tests pass via `pytest`
* [ ] Developed and tested within WSL environment using Poetry


