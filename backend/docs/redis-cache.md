# Redis cache

Redis caches completed generation workflows and generated Playwright scripts.

## Cached data

- Original user stories, epics, and features (inside `input_payload`)
- Prepared structured context
- Validated test scenarios and validation result
- Validated test cases and validation result
- Generated Playwright source, page metadata, and discovered elements

Workflow cache keys are SHA-256 fingerprints of normalized input, mock/live mode,
and Cerebras model settings. Script keys include the scenarios, test cases, and
application URL. Raw input and API keys are never placed in Redis key names.

## Start Redis

With Docker installed:

```powershell
docker compose up -d redis
```

Alternatively, start Redis 7 locally or in WSL on port 6379.

Then restart the backend and verify:

```text
GET http://localhost:8001/health/cache
```

A healthy response confirms caching is active. If Redis is unavailable, cache
operations are skipped and the existing live generation workflow continues.

Default workflow and script TTLs are 24 hours. Configure them with
`REDIS_WORKFLOW_TTL_SECONDS` and `REDIS_SCRIPT_TTL_SECONDS`.
