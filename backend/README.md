# Test Case Generator Backend 2

FastAPI persistence and review service for versioned test scenarios and test cases.

## Local setup

Use Python 3.12, copy `.env.example` to `.env`, create a dedicated PostgreSQL database, then run:

```powershell
cd "E:\Cloud Destinations\Test Case Generation"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
cd backend
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Swagger is at `http://localhost:8001/docs`. Do not point tests at development or production data.

Docker alternative: `docker compose up --build`.

## PostgreSQL on Windows

Check whether PostgreSQL is installed, running, and listening:

```powershell
Get-Service *postgres*
Start-Service postgresql-x64-16  # replace with the service name shown above
Get-NetTCPConnection -LocalPort 5432 -State Listen
netstat -ano | findstr :5432
psql -U postgres -h 127.0.0.1 -p 5432 -d postgres
```

Create the database from `psql` if it does not exist:

```sql
SELECT 'CREATE DATABASE testcase_generator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'testcase_generator')\gexec
```

Alternatively, start PostgreSQL with Docker while running FastAPI locally:

```powershell
docker compose up -d postgres
docker compose ps
```

Use `127.0.0.1` in `DATABASE_URL` for a local FastAPI process. The Compose
backend uses the `postgres` service hostname internally. Set the real local
PostgreSQL password only in `.env`; never commit it.

Run and inspect migrations:

```powershell
alembic current
alembic history
alembic upgrade head
```

The repository's `.venv` is machine-specific and should not be reused after a
clone. Delete it locally and create a fresh Python 3.12 environment with the
commands above. Run the Person 2 test suite with `pytest tests/unit/repositories
tests/integration tests/api/test_project_api.py tests/api/test_scenario_api.py
tests/api/test_testcase_api.py` as those suites are added.

## Backend 1 integration

Manual inputs are versioned in `project_inputs`. API integration reads `GET /projects/{project_id}/approved-context`. Shared-database integration intentionally requires an agreed mapping before use so Backend 1 table names are not spread through this service.

Regeneration endpoints persist mandatory feedback and return a stable `workflow_hook`; Person 1's workflow service should consume that hook rather than routers calling an LLM.
