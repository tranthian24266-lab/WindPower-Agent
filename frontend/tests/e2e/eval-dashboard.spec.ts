import { expect, test } from "@playwright/test";

test("eval dashboard loads suite list", async ({ page }) => {
  await page.goto("/evals");
  await expect(page.getByText("Eval Dashboard")).toBeVisible();
  await expect(page.getByText("Fault Diagnosis Smoke")).toBeVisible();
  await expect(page.getByText("RUL Prediction Smoke")).toBeVisible();
  await expect(page.getByText("Anomaly Report Smoke")).toBeVisible();
});
