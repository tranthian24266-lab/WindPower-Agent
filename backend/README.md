# Backend

## What Lives Here

- FastAPI application entrypoint: `app/main.py`
- Settings and path resolution: `app/core/settings.py`
- Write-auth dependency: `app/core/auth.py`
- Report generation, model routing, chat, and knowledge-base services
- SQLite schema and migrations under `app/db/`

## Required External Dependency

Set or make available a `littlemodel` workspace. Resolution order is:

1. `WINDPOWER_LITTLEMODEL_ROOT`
2. legacy `LITTLEMODEL_ROOT`
3. auto-discovery of the sibling folder `../littlemodel`

If none of these resolve, backend startup fails fast by design.

## Environment Setup

Use one of the example files:

- Minimal startup mode: [backend/.env.example](/C:/Users/luzian/Desktop/windpower_agent3/backend/.env.example)
- Full-features mode: [backend/.env.full-features.example](/C:/Users/luzian/Desktop/windpower_agent3/backend/.env.full-features.example)

Key toggles:

- `WINDPOWER_AUTH_ENABLED`
- `WINDPOWER_API_KEY`
- `WINDPOWER_BASE_REPORT_PDF_ENABLED`
- `WINDPOWER_ENHANCED_REPORTS_ENABLED`
- `WINDPOWER_KNOWLEDGE_RAG_ENABLED`
- `WINDPOWER_CHAT_RAG_ENABLED`
- `WINDPOWER_QDRANT_ENABLED`
- `WINDPOWER_QDRANT_URL`

## Run Locally

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Useful read-only endpoints:

- Health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- Config summary: [http://127.0.0.1:8000/api/system/config-summary](http://127.0.0.1:8000/api/system/config-summary)
- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Auth Mode

When `WINDPOWER_AUTH_ENABLED=true`, write routes require the `X-API-Key` header. Read-only routes remain open.

Protected writes include:

- `/api/upload`
- `/api/diagnose`
- `/api/reports/*/generate`
- `/api/enhanced-reports/*/generate`
- `/api/model-catalog/sync`
- `/api/model-catalog/model-versions/*/validate`
- `/api/model-catalog/models/*/aliases/*`
- `/api/knowledge/ingest`
- `/api/knowledge/reindex`

## Test Commands

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q
```
