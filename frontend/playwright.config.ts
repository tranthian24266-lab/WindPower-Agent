import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const currentDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,
  timeout: 120000,
  expect: {
    timeout: 15000,
  },
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8010",
      cwd: path.join(currentDir, "..", "backend"),
      url: "http://127.0.0.1:8010/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: "cmd /c \"set VITE_DEV_PROXY_TARGET=http://127.0.0.1:8010&& npm run dev -- --host 127.0.0.1 --port 5174\"",
      cwd: currentDir,
      url: "http://127.0.0.1:5174",
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
  ],
});
