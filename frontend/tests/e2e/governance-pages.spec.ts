import { expect, test } from "@playwright/test";

test("specialist and audit governance pages load", async ({ page }) => {
  await page.goto("/specialists");
  await expect(page.getByText("专家智能体监控", { exact: true })).toBeVisible();
  await expect(page.getByText("Recent Handoffs", { exact: true })).toBeVisible();

  await page.goto("/audit");
  await expect(page.getByText("审计日志", { exact: true })).toBeVisible();
  await expect(page.getByText("最新审计记录", { exact: true })).toBeVisible();
});
