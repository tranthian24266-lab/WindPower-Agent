import path from "node:path";

import { expect, test } from "@playwright/test";

const littlemodelRoot = process.env.WINDPOWER_LITTLEMODEL_ROOT || "C:/Users/luzian/Desktop/littlemodel";
const faultSamplePath = path.join(littlemodelRoot, "fault_diagnosis", "test_data", "test_sensor1_x.npy");
const rulSamplePath = path.join(
  littlemodelRoot,
  "rul_prediction",
  "test_data",
  "split_60_40",
  "data-20130406T221209Z.mat",
);
const anomalySamplePath = path.join(littlemodelRoot, "anomaly_detection", "test_data", "test_data_sample.csv");

async function runDiagnosisToCaseDetail(page: import("@playwright/test").Page, taskIndex: number, samplePath: string) {
  await page.goto("/diagnosis");
  await page.locator(".choice-card").nth(taskIndex).click();
  await page.locator('input[type="file"]').setInputFiles(samplePath);
  await page.locator(".run-row .action-button").click();
  await page.waitForURL(/\/cases\/.+/, { timeout: 120000 });
  await expect(page).toHaveURL(/\/cases\/.+/);
}

test("main user flow covers model view, diagnosis, report generation, and chat", async ({ page }) => {
  test.slow();

  let caseId = "";

  await test.step("open dashboard and model library", async () => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "模型库" })).toBeVisible();
    await page.getByRole("link", { name: "模型库" }).click();
    await expect(page).toHaveURL(/\/models$/);
  });

  await test.step("upload a fault sample and reach case detail", async () => {
    await runDiagnosisToCaseDetail(page, 0, faultSamplePath);
    caseId = page.url().split("/").pop() || "";
  });

  await test.step("generate the base report and open the report center", async () => {
    await page.locator(".button-row .action-button").first().click();
    await page.waitForURL(/\/reports\/.+/, { timeout: 120000 });
    await expect(page.getByText("报告中心")).toBeVisible();
  });

  await test.step("send a chat question for the generated case", async () => {
    await page.goto(`/chat?caseId=${caseId}`);
    await page.locator("textarea.chat-input").fill("请用一句话总结这个案例。");
    await page.locator(".filters-row .action-button").click();
    await expect(page.locator(".chat-bubble.assistant").last()).toBeVisible({ timeout: 120000 });
  });
});

test("rul diagnosis reaches case detail", async ({ page }) => {
  test.slow();

  await runDiagnosisToCaseDetail(page, 1, rulSamplePath);
  await expect(page).toHaveURL(/\/cases\/.+/);
});

test("anomaly diagnosis reaches case detail", async ({ page }) => {
  test.slow();

  await runDiagnosisToCaseDetail(page, 2, anomalySamplePath);
  await expect(page).toHaveURL(/\/cases\/.+/);
});
