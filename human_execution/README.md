# Human Execution

`human_execution` is an isolated extension for recording a business flow in a
headed Playwright browser, generating a stable Python Playwright script, and
handing that script to the existing automation execution and comparison
pipeline.

The module owns its API, standalone UI, services, browser lifecycle, models,
tests, and the following database tables:

- `human_execution_sessions`
- `human_execution_actions`
- `human_execution_scripts`

## Run as a standalone extension

From the repository root:

```powershell
$env:HUMAN_EXECUTION_EMAIL = "automation@example.com"
$env:HUMAN_EXECUTION_PASSWORD = "runtime-secret"
.\.venv\Scripts\python.exe -m uvicorn human_execution.api:app --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010`. The database tables are created from the
extension's separate SQLAlchemy metadata during startup.

For local UI development without PostgreSQL:

```powershell
$env:HUMAN_EXECUTION_MEMORY_STORE = "true"
```

Memory storage is not intended for production because sessions would not be
durable.

## Clean host integration

The package exports a FastAPI `router` under `/human-execution` and a
`create_app()` factory. A host may mount the standalone ASGI app or include the
router at its composition boundary; no automation service implementation needs
to change.

This repository includes that router through `/api/v1/human-execution` and
connects the existing Automation page's **Manual execution** selection to it.
Choose Manual execution and click **Start Manual Execution** to launch the
headed browser directly from the current frontend.

## Workflow

1. `POST /api/human-execution/sessions` creates a session in
   `waiting_for_human` and launches Chromium in headed mode.
2. The session moves to `recording`. Same-origin click, fill, selection,
   checkbox, radio, and navigation events are captured.
3. `POST /sessions/{id}/finish` checks that the browser is open,
   authentication is complete, and executable actions exist.
4. Stable locators are generated in this order: test ID, label, role/name,
   placeholder, stable ID/CSS, exact visible text.
5. Password input is persisted only as `<REDACTED>` and is emitted as the
   `HUMAN_EXECUTION_PASSWORD` environment lookup.
6. The script is syntax- and policy-validated, stored with workflow/scenario/
   test-case references, and published using the existing generation manifest.
7. The generated-script panel exposes **Execute with Playwright**. That action
   uses the current execution, evidence, mapping, comparison, and report
   pipeline without replacing it.

The UI connects to `/sessions/{id}/live` and displays the live state, browser
status, and recorded action count. It provides Start Manual Execution, Finish
Recording, and Cancel Session controls.
