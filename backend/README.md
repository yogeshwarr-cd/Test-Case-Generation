# Test Case Generator Backend 2

FastAPI persistence and review service for versioned test scenarios and test cases.

## Local setup

Use Python 3.12, copy `.env.example` to `.env`, create a dedicated PostgreSQL database, then run:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Swagger is at `http://localhost:8001/docs`. Do not point tests at development or production data.

Docker alternative: `docker compose up --build`.

## Backend 1 integration

Manual inputs are versioned in `project_inputs`. API integration reads `GET /projects/{project_id}/approved-context`. Shared-database integration intentionally requires an agreed mapping before use so Backend 1 table names are not spread through this service.

Regeneration endpoints persist mandatory feedback and return a stable `workflow_hook`; Person 1's workflow service should consume that hook rather than routers calling an LLM.
