import { chromium } from "playwright";
import * as path from "path";
import * as fs from "fs";

const SCREENSHOTS_DIR = path.join(__dirname, "test-reports", "screenshots");

async function captureScreenshots() {
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();

  const baseUrl = "http://127.0.0.1:5173";

  try {
    // 1. Dashboard
    await page.goto(`${baseUrl}/`);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "1_dashboard.png") });
    console.log("Captured Dashboard");

    // 2. Model Library
    await page.goto(`${baseUrl}/models`);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "2_models.png") });
    console.log("Captured Model Library");

    // 3. Diagnosis
    await page.goto(`${baseUrl}/diagnosis`);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "3_diagnosis.png") });
    console.log("Captured Diagnosis");

    // 4. Cases
    await page.goto(`${baseUrl}/cases`);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "4_cases.png") });
    console.log("Captured Cases");

    // 5. Reports
    await page.goto(`${baseUrl}/reports`);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "5_reports.png") });
    console.log("Captured Reports");

    // 6. Chat
    await page.goto(`${baseUrl}/chat`);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "6_chat.png") });
    console.log("Captured Chat");

    // 7. Knowledge Base
    await page.goto(`${baseUrl}/knowledge`);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "7_knowledge.png") });
    console.log("Captured Knowledge Base");

  } catch (error) {
    console.error("Error capturing screenshots:", error);
  } finally {
    await browser.close();
  }
}

captureScreenshots();
