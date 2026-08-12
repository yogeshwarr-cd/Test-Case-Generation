# Playwright execution and Seacrawl recovery

The automation feature is downstream of the completed generation workflow. It reads validated test cases but does not mutate workflow state or call the existing LLM provider client.

## Flow

1. Open the completed results page and select **Proceed to Test Scripts**.
2. Enter a reachable deployed application URL.
3. The backend opens the page with Chromium, records accessible UI controls, and generates Python Playwright Page Object scripts.
4. Review or download each script.
5. Choose automated execution or a manual package.
6. Automated runs capture status, duration, console output, network failures, screenshots, stack traces, Seacrawl recovery state, and traceability IDs.

Install and start the backend:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m playwright install chromium
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8006
```

Readiness is available at `GET /api/v1/automation/health`.

## Seacrawl service

Seacrawl is an optional separate service under `services/seacrawl`, pinned for this integration to commit `2700c299135989a8fbbf36f5717efcd74605b780` (repository version `1.0.47`). Its Python requirement is `>=3.11,<3.14`, but its FastAPI, browser, database, and transitive dependency set differs from this backend. Keep it in its own environment or Docker Compose stack.

```powershell
cd services/seacrawl
Copy-Item .env.example .env
docker compose up -d
```

Then configure the test-case backend:

```env
SEACRAWL_FALLBACK_ENABLED=true
SEACRAWL_INTEGRATION_MODE=self_hosted
SEACRAWL_BASE_URL=http://localhost:8000
SEACRAWL_API_KEY=
SEACRAWL_TIMEOUT_SECONDS=30
SEACRAWL_MAX_ATTEMPTS=1
SEACRAWL_MAX_CALLS_PER_TEST=2
SEACRAWL_MAX_CALLS_PER_RUN=20
```

When enabled, Seacrawl is called only after a Playwright locator or action timeout. It identifies a replacement selector; Playwright retries that failed action and remains the execution engine.

## License warning

The cloned Seacrawl source is GNU AGPL-3.0. Network deployment or modifications can create source-disclosure obligations. Keep the service boundary and obtain legal review before distributing a combined product or offering a modified Seacrawl service. This is a compatibility warning, not legal advice.
