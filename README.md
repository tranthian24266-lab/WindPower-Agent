# Windpower Small Model Diagnostic Platform

This repository packages a windpower diagnostic platform around the verified local model library at `C:\Users\luzian\Desktop\littlemodel`.

## Current Platform Scope

- FastAPI backend for upload, diagnosis, cases, reports, chat, model catalog, and knowledge-base operations
- React + Vite frontend for model browsing, diagnosis execution, case review, reports, and chat
- Base report and enhanced report chains with explicit export status
- Optional RAG/Qdrant integration and optional write-auth via `X-API-Key`
- Automated backend tests plus three Playwright end-to-end diagnosis/report flows

## Hard Constraints

- Do not modify model code, weights, or test data inside `C:\Users\luzian\Desktop\littlemodel`
- Use the unified `model_registry.json` + `inference.py:predict` entrypoints only
- Treat `littlemodel` as an external dependency that must stay intact

## Quick Start

- Backend guide: [backend/README.md](/C:/Users/luzian/Desktop/windpower_agent3/backend/README.md)
- Frontend guide: [frontend/README.md](/C:/Users/luzian/Desktop/windpower_agent3/frontend/README.md)
- End-to-end run guide: [RUN_GUIDE.md](/C:/Users/luzian/Desktop/windpower_agent3/RUN_GUIDE.md)
- Deployment notes: [docs/deployment-notes.md](/C:/Users/luzian/Desktop/windpower_agent3/docs/deployment-notes.md)
- Security mode notes: [docs/security-mode.md](/C:/Users/luzian/Desktop/windpower_agent3/docs/security-mode.md)
- Testing playbook: [docs/testing-playbook.md](/C:/Users/luzian/Desktop/windpower_agent3/docs/testing-playbook.md)
- Project slimming note: [docs/project-slimming-2026-06-07.md](/C:/Users/luzian/Desktop/windpower_agent3/docs/project-slimming-2026-06-07.md)

## Current Validation Entry Points

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q

cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm run build
npx playwright test
```
