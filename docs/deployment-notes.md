# Deployment Notes

## Environment Profiles

### Local Development

- `WINDPOWER_DATABASE_URL=` keeps SQLite enabled
- `WINDPOWER_AUTH_ENABLED=false`
- `WINDPOWER_RBAC_ENABLED=false`
- `WINDPOWER_AUDIT_ENABLED=true`
- Frontend can use relative `/api`

### Staging

- Prefer PostgreSQL via `WINDPOWER_DATABASE_URL`
- Enable `WINDPOWER_AUTH_ENABLED=true`
- Enable `WINDPOWER_RBAC_ENABLED=true`
- Keep `WINDPOWER_AUDIT_ENABLED=true`
- Point `VITE_API_BASE_URL` to the staging backend if not using same-origin routing

### Production

- PostgreSQL is recommended as the primary database
- Keep `WINDPOWER_AUTH_ENABLED=true`
- Keep `WINDPOWER_RBAC_ENABLED=true`
- Keep `WINDPOWER_AUDIT_ENABLED=true`
- Keep `WINDPOWER_OBSERVABILITY_ENABLED=true`
- Use reverse proxy or same-origin deployment for `/api`

## Backend Checklist

- Ensure `littlemodel` is reachable via `WINDPOWER_LITTLEMODEL_ROOT` or sibling auto-discovery
- Verify `/api/system/config-summary`
- Verify `/api/system/observability-summary`
- Verify `/api/system/audit-summary`
- Verify `/api/system/specialist-summary`

## Frontend Checklist

- `npm run build`
- Specialist page `/specialists` loads
- Audit page `/audit` loads
- Run detail page shows handoff timeline

## Reports

- Base HTML reports work without extra PDF dependencies
- Base PDF export depends on WeasyPrint availability unless `WINDPOWER_BASE_REPORT_PDF_ENABLED=false`

## Qdrant

- Local startup file: [docker-compose.qdrant.yml](/C:/Users/luzian/Desktop/windpower_agent3/docker-compose.qdrant.yml)
- If remote Qdrant is used, set `WINDPOWER_QDRANT_ENABLED=true` and `WINDPOWER_QDRANT_URL`
- Local smoke can be verified with `GET /api/knowledge/index-status` and `POST /api/knowledge/reindex`

## Pre-Deployment Verification

- Backend `pytest -q` passes
- Frontend `npm run build` passes
- Frontend `CI=1 npx playwright test` passes
- `/api/system/config-summary` reflects the target database/auth/RBAC/audit configuration
