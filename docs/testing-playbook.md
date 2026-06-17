# Testing Playbook

## Backend Regression

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q
```

## Frontend Build

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm run build
```

## Frontend E2E

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npx playwright test
```

## Main E2E Coverage Today

- Open dashboard and model library
- Upload a real fault sample, reach case detail, generate a base report, and open chat
- Upload a real RUL sample and reach case detail
- Upload a real anomaly sample and reach case detail

## Manual Qdrant Smoke

```powershell
docker compose -f C:\Users\luzian\Desktop\windpower_agent3\docker-compose.qdrant.yml up -d

# Start an isolated backend instance if :8000 is already occupied
cd C:\Users\luzian\Desktop\windpower_agent3\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010

# In another terminal
Invoke-RestMethod -Uri http://127.0.0.1:8010/api/system/config-summary
Invoke-RestMethod -Uri http://127.0.0.1:8010/api/knowledge/index-status
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/knowledge/reindex -ContentType 'application/json' -Body '{"force_recreate": true}'
Invoke-RestMethod -Uri http://127.0.0.1:8010/api/knowledge/index-status
```

## Known Gaps

- The E2E suite covers three primary diagnosis entry paths, but not every auth/report/export edge case
- Live Docker/Qdrant startup is validated manually rather than by the automated test suite
