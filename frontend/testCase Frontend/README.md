# Test Case Generation frontend

This feature extends the existing Next.js application with a separate, type-safe UI for the Test Case Generation backend.

## Structure

- `components/` reusable feature UI
- `pages/` input, progress, review, and results screens
- `services/testCaseApi.ts` dedicated API and SSE client
- `store/workflowStore.ts` active workflow state and session persistence
- `types/`, `utils/`, and `constants/` API models and shared logic

The public App Router entry points live under `app/test-case-generation` and render these feature pages.

## Environment

Set the second backend base URL:

```env
NEXT_PUBLIC_TESTCASE_API_BASE_URL=http://127.0.0.1:8003
```

The existing `NEXT_PUBLIC_API_BASE_URL` is not changed.

## Routes

- `/test-case-generation` — manual requirement input
- `/test-case-generation/progress` — SSE workflow progress
- `/test-case-generation/review` — manual scenario or test-case review
- `/test-case-generation/results` — results dashboard

## API integration

- `POST /api/v1/workflows/start`
- `GET /api/v1/workflows/{workflow_id}`
- `GET /api/v1/workflows/{workflow_id}/events`
- `POST /api/v1/workflows/{workflow_id}/resume`
- `GET /api/v1/workflows/{workflow_id}/result`

Only the workflow ID, project ID, and latest progress snapshot are persisted in session storage.

## Run and verify

```bash
npm run dev
npm run lint
npm run build
```
