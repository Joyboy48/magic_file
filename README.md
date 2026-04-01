# Async Document Processing Workflow (FastAPI + Celery + Next.js)

This project implements a production-style asynchronous document pipeline:
- Upload one or more files
- Persist document + job state in PostgreSQL
- Process in background using Celery workers
- Publish progress events from workers through Redis Pub/Sub
- Stream near-real-time progress in the UI
- Review/edit extracted output, finalize, and export as JSON/CSV

## Tech Stack

- Frontend: Next.js + React + TypeScript
- Backend: FastAPI (Python)
- Database: PostgreSQL
- Queue/Workers: Celery
- Messaging/State: Redis (broker + result backend + Pub/Sub)

## Architecture Overview

### Backend (FastAPI)
- Handles upload, list, detail, retry, review update, finalize, export.
- Stores metadata and processing state in PostgreSQL.
- Exposes SSE endpoint to stream progress events to frontend.

### Worker Layer (Celery)
- Receives jobs from Redis broker.
- Executes multi-stage background workflow.
- Publishes progress events at each stage via Redis Pub/Sub.

### Redis
- Celery broker/result backend
- Pub/Sub channel for per-job progress events (`job_progress:{job_id}`)

### Frontend (Next.js)
- Upload page
- Jobs dashboard with search/filter/sort
- Job detail page for progress, review/edit, finalize, export

## Document Processing Stages

Each job emits progress events for:
- `job_queued`
- `job_started`
- `document_parsing_started`
- `document_parsing_completed`
- `field_extraction_started`
- `field_extraction_completed`
- `final_result_stored`
- `job_completed` / `job_failed`

## API Surface

- `POST /api/upload` — upload one or more files and enqueue jobs
- `GET /api/jobs` — list jobs with search/filter/sort
- `GET /api/jobs/{job_id}` — job detail
- `GET /api/jobs/{job_id}/events` — SSE progress stream
- `POST /api/jobs/{job_id}/retry` — retry failed job
- `PATCH /api/jobs/{job_id}/reviewed` — save reviewed JSON
- `POST /api/jobs/{job_id}/finalize` — finalize reviewed result
- `GET /api/jobs/{job_id}/export?format=json|csv` — export finalized result

## Run (Docker Compose)

1) (Optional) copy env file:
```bash
cp .env.example .env
```

2) Start all services:
```bash
docker compose up --build -d
```

3) Open apps:
- Frontend: `http://localhost:3100`
- Backend API: `http://localhost:8001`
- Swagger: `http://localhost:8001/docs`

4) Stop services:
```bash
docker compose down
```

## How To Test Quickly

1) Upload file from UI:
- Open `http://localhost:3100/upload`
- Upload `samples/sample1.txt` or `samples/sample2.txt`

2) Validate workflow:
- Job should move `queued -> processing -> completed`
- Job detail shows extracted JSON + editable reviewed JSON

3) Finalize and export:
- Click `Finalize`
- Export `JSON` and `CSV`

4) Retry test:
- Upload a file with `fail` in its filename (e.g. `my_fail_case.txt`)
- Job should fail and show `Retry` action

## Requirements Coverage (Mandatory)

- Upload one or more documents: ✅
- Save metadata and jobs in PostgreSQL: ✅
- Celery background processing (outside request cycle): ✅
- Redis Pub/Sub progress events from worker: ✅
- Status states (queued/processing/completed/failed): ✅
- Live progress visibility in frontend: ✅ (SSE)
- Dashboard with search/filter/sort: ✅
- Detail page with review/edit: ✅
- Finalization flow: ✅
- Retry failed jobs: ✅
- Export finalized records as JSON/CSV: ✅

## Assumptions / Tradeoffs / Limitations

- Processing logic is intentionally simple (no OCR/AI quality focus).
- Text extraction is heuristic/mock for non-text/binary documents.
- SQLAlchemy `create_all()` is used (no Alembic migrations in this scaffold).
- SSE stream is real-time; if page opens after completion, event panel may be empty.
- No authentication/authorization.

## Samples

- Input files: `samples/`
- Sample exports: `samples/exports/finalized-sample.json`, `samples/exports/finalized-sample.csv`

## Demo Video (3–5 minutes)

Record and include:
- Upload flow
- Live/near-real-time job progress
- Dashboard search/filter/sort
- Review/edit and finalize
- Export JSON + CSV
- Failed job retry flow

## AI Tools Used

Development assistance was used for code generation, debugging, and documentation refinement.

