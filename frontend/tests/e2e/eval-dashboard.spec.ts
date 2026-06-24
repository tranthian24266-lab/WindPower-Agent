import { expect, test } from "@playwright/test";

test("eval dashboard loads suite list", async ({ page }) => {
  await page.goto("/evals");
  await expect(page.getByText("评测仪表盘", { exact: true })).toBeVisible();
  await expect(page.getByText("Fault Diagnosis Smoke", { exact: true })).toBeVisible();
  await expect(page.getByText("RUL Prediction Smoke", { exact: true })).toBeVisible();
  await expect(page.getByText("Anomaly Report Smoke", { exact: true })).toBeVisible();
});
