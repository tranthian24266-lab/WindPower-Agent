import path from "node:path";

import { expect, test } from "@playwright/test";


const littlemodelRoot = path.resolve(process.cwd(), "..", "littlemodel");
const samples = [
  path.join(littlemodelRoot, "fault_diagnosis", "test_data", "test_sensor1_x.npy"),
  path.join(littlemodelRoot, "rul_prediction", "test_data", "split_60_40", "data-20130406T221209Z.mat"),
  path.join(littlemodelRoot, "anomaly_detection", "test_data", "test_data_sample.csv"),
];


for (const [index, samplePath] of samples.entries()) {
  test(`smart diagnosis automatically routes packaged sample ${index + 1}`, async ({ page }) => {
    test.slow();
    await page.goto("/diagnosis");
    await expect(page.getByRole("button", { name: "开始智能诊断" })).toBeVisible();
    await page.locator('input[type="file"]:not([multiple])').setInputFiles(samplePath);
    await page.getByRole("button", { name: "开始智能诊断" }).click();
    await page.waitForURL(/\/cases\/.+/, { timeout: 120000 });
    await expect(page).toHaveURL(/\/cases\/.+/);
  });
}
