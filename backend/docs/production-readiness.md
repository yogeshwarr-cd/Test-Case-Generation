# Production readiness notes

## Workflow

Requirement -> Scenario -> Test Case -> Automation Intent -> Playwright Script -> Execution -> Failure Analysis -> Report

Requirements are generated and validated first. The automation workflow discovers the deployed application, builds scripts, executes them, captures evidence, and compares execution coverage with requirement artifacts.

## Local startup

```powershell
cd backend
& ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

In another terminal:

```powershell
cd frontend
npm.cmd run dev
```

The frontend is available at `http://localhost:3000`; API documentation is available at `http://127.0.0.1:8001/docs`.

## Verification

```powershell
cd backend
& ..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests\unit tests\api
cd ..\frontend
npm.cmd exec tsc -- --noEmit --incremental false
```

Run `npm.cmd run build` after stopping an active Next.js development server; on Windows, that server can lock files under `.next`.

## Deployment checklist

- Keep secrets, database URLs, provider keys, and storage paths in deployment secret management.
- Apply migrations before starting the API.
- Expose the API health endpoint to the process supervisor.
- Start frontend and backend under a supervisor with graceful shutdown.
- Retain execution artifacts in configured storage and avoid logging credentials or tokens.
- Verify the complete workflow with a local deterministic demo application before public sites.

## Known limitations

Public demo applications can block automation through bot protection, authentication, or network policy. Such crawls must be reported as blocked or partial coverage. Legacy frontend lint findings outside the automation feature remain separate cleanup work and must not be hidden by disabling lint rules.
