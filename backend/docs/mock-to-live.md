# Mock mode and live-mode handoff

The backend currently runs with `APP_MOCK_MODE=true`.

Mock mode preserves the real input preparation, orchestration, Pydantic schemas, validation, regeneration routing, API contracts, frontend flow, Playwright script generation, reports, and traceability. It replaces external LLM calls with deterministic schema-valid scenario and test-case responses. Skyvern and deployed-site/browser calls are disabled or simulated.

Confirm the current mode with `GET /health`; it returns `"mode": "mock"`.

## Connect live

After code verification, edit only `backend/.env`:

```env
APP_MOCK_MODE=false
```

Keep the required provider and optional Skyvern keys configured, then restart the backend. Confirm `GET /health` returns `"mode": "live"` and `GET /api/v1/automation/health` reports the real browser/service state.

Never switch to live mode in shared CI or developer environments until API quotas, target URLs, database selection, and secret storage have been reviewed.
