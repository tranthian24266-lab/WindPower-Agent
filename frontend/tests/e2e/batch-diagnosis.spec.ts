import path from "node:path";

import { expect, test } from "@playwright/test";

const littlemodelRoot = path.resolve(process.cwd(), "..", "littlemodel");
const samples = [
  path.join(littlemodelRoot, "fault_diagnosis", "test_data", "test_sensor1_x.npy"),
  path.join(littlemodelRoot, "rul_prediction", "test_data", "split_60_40", "data-20130406T221209Z.mat"),
  path.join(littlemodelRoot, "anomaly_detection", "test_data", "test_data_sample.csv"),
];

test("batch diagnosis routes every packaged sample and exposes its timeline", async ({ page }) => {
  test.slow();
  await page.goto("/diagnosis");

  const batchInput = page.locator('input[type="file"][multiple]');
  const batchPanel = batchInput.locator("xpath=ancestor::article");
  await batchInput.setInputFiles(samples);
  await expect(batchPanel.locator("strong").filter({ hasText: "3" })).toBeVisible();
  await batchPanel.locator("button.action-button").click();

  await expect(batchPanel.locator(".list-card")).toHaveCount(3, { timeout: 180000 });
  await expect(batchPanel.getByRole("button", { name: "查看诊断案例" })).toHaveCount(3);
  await expect(batchPanel.getByRole("button", { name: "查看 Agent 时间线" })).toHaveCount(3);
});
