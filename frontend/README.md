# Frontend

## What Lives Here

- React + TypeScript + Vite application
- Runtime API client in `src/lib/api.ts`
- Session-only local API key helper for write-auth testing
- Playwright configuration and E2E tests under `tests/e2e/`

## Runtime Configuration

Frontend API origin is controlled by `VITE_API_BASE_URL`.

- Example files:
  - [frontend/.env.example](/C:/Users/luzian/Desktop/windpower_agent3/frontend/.env.example)
  - [frontend/.env.development.example](/C:/Users/luzian/Desktop/windpower_agent3/frontend/.env.development.example)
- Recommended default: `VITE_API_BASE_URL=/`
- Local development uses the Vite `/api` proxy to `http://127.0.0.1:8000`

## Run Locally

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm install
npm run dev
```

Dev server notes:

- Local dev is pinned to `http://127.0.0.1:5173`
- `strictPort` is enabled, so a second frontend instance now fails fast instead of silently moving to `5174`
- If startup fails because `5173` is already in use, reuse the running instance or stop the old one first

## Available Scripts

```powershell
npm run dev
npm run build
npm run preview
npm run e2e
```

## Local Write-Auth Support

When backend write-auth is enabled, the sidebar includes a session-only API key input.

- The key is stored in browser `sessionStorage`
- It is attached as `X-API-Key` on outgoing frontend requests
- It is not embedded into the build output
