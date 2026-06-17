import { expect, test } from "@playwright/test";

test("specialist and audit governance pages load", async ({ page }) => {
  await page.goto("/specialists");
  await expect(page.getByText("Specialist Dashboard")).toBeVisible();
  await expect(page.getByText("Recent Handoffs")).toBeVisible();

  await page.goto("/audit");
  await expect(page.getByText("Audit Logs")).toBeVisible();
  await expect(page.getByText("Recent Audit Entries")).toBeVisible();
});
