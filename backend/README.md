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
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8003
```

Swagger is at `http://localhost:8003/docs`. Do not point tests at development or production data.

## Optional wireframe and screenshot analysis

The input form uses a two-step flow: `POST /api/v1/images/upload` analyzes and stores an optional image locally, then the normal `POST /api/v1/workflows/start` request references the returned `image_id`. The existing workflow is unchanged when `image_ids` is empty.

Images are validated, orientation-corrected, resized, metadata-stripped, OCR-optimized, analyzed with local PaddleOCR (Tesseract fallback), and passed through a configured YOLO UI detector. If custom weights are unavailable, OpenCV contour heuristics keep the workflow operational. OCR labels are coordinate-matched to controls, the screen is classified with rules, and only compact JSON is fused into the existing scenario/test-case prompts. Raw images, OCR blocks, and bounding boxes are not sent to text LLMs.

Identical images reuse SHA-256 cached analysis under `IMAGE_STORAGE_PATH`; no additional vision-LLM call occurs. Vision fallback is disabled by default. A screenshot cannot prove backend behavior, authorization, database/API behavior, performance, or security rules; textual requirements remain authoritative.

Upload example:

```powershell
curl.exe -X POST http://localhost:8003/api/v1/images/upload -F "image=@login.png" -F "image_description=Customer login wireframe"
```

Then include `"image_ids":["<returned-uuid>"]` inside `input_payload` when starting the existing workflow. Inspect and test both endpoints at `http://localhost:8003/docs`.

Install runtime dependencies with `pip install -r requirements.txt`. For PaddleOCR and YOLO training use `pip install -r requirements-ml.txt` plus the platform-appropriate PaddlePaddle runtime. Tesseract fallback also requires the local Tesseract executable.

YOLO dataset layout and annotation rules live under `../ml/`. Train, validate, and export:

```powershell
python ..\ml\training\train_yolo.py --device cpu --epochs 100 --batch 16 --imgsz 960
python ..\ml\training\validate_yolo.py --model ..\ml\runs\ui_detector\weights\best.pt
python ..\ml\training\export_yolo.py --model ..\ml\runs\ui_detector\weights\best.pt
```

Run image tests with `pytest tests/unit/image_processing -q`. Detector accuracy depends on the quality and quantity of annotated UI screenshots; heuristic detections deliberately carry lower confidence.

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
