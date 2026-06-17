# Run Guide

## 1. Model Library

Preferred bundled path:

```text
C:\Users\luzian\Desktop\windpower_agent3\littlemodel
```

You can also point `WINDPOWER_LITTLEMODEL_ROOT` to an external `littlemodel` path if needed.

## 2. Backend Startup

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Useful checks:

- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- Config summary: [http://127.0.0.1:8000/api/system/config-summary](http://127.0.0.1:8000/api/system/config-summary)

## 3. Optional Qdrant Startup

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3
docker compose -f docker-compose.qdrant.yml up -d
```

## 4. Frontend Startup

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm install
npm run dev
```

Frontend URL:

- [http://127.0.0.1:5173](http://127.0.0.1:5173)
- The frontend now uses a strict dev port. If `5173` is occupied, Vite will fail instead of quietly opening `5174`.

## 5. Suggested Manual Acceptance Flow

1. Open the dashboard at [http://127.0.0.1:5173](http://127.0.0.1:5173).
   Expected: the sidebar, dashboard cards, and navigation links render without API errors.
2. Open Model Library.
   Expected: model groups and versions load successfully.
3. Open Diagnosis and run the fault-diagnosis sample below.
   Expected: the page navigates to a case detail page with `Case Overview` and `Routing Trace`.
4. From that case detail page, click `Generate Report`.
   Expected: the app opens `Report Center`, base-report preview loads, and HTML download is available.
5. Open Chat for the same case and ask one short question.
   Expected: an assistant reply appears and the case context is preserved.
6. Return to Diagnosis and run the RUL sample below.
   Expected: a second case detail page opens and shows the RUL result metrics plus routing trace.
7. Return to Diagnosis and run the anomaly sample below.
   Expected: a third case detail page opens and shows anomaly metrics plus routing trace.
8. Open [http://127.0.0.1:8000/api/system/config-summary](http://127.0.0.1:8000/api/system/config-summary).
   Expected: `littlemodel_root_exists=true` and the current feature flags match the intended environment.
9. Open [http://127.0.0.1:8000/api/knowledge/index-status](http://127.0.0.1:8000/api/knowledge/index-status).
   Expected: `remote_available=true`, `remote_collection_exists=true`, and `payload_indexes` contains the metadata fields.

## 6. Sample Files

- Fault diagnosis:
  `C:\Users\luzian\Desktop\windpower_agent3\littlemodel\fault_diagnosis\test_data\test_sensor1_x.npy`
- RUL prediction:
  `C:\Users\luzian\Desktop\windpower_agent3\littlemodel\rul_prediction\test_data\split_60_40\data-20130406T221209Z.mat`
- Anomaly detection:
  `C:\Users\luzian\Desktop\windpower_agent3\littlemodel\anomaly_detection\test_data\test_data_sample.csv`

## 7. Validation Commands

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q

cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm run build
npx playwright test
```
