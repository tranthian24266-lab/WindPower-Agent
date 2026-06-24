import { expect, test } from "@playwright/test";


test("model library exposes the managed model upload workflow", async ({ page }) => {
  await page.goto("/models");

  const addModelButton = page.getByRole("button", { name: "添加模型" });
  await expect(addModelButton).toBeVisible();
  await addModelButton.click();

  await expect(page.getByText("添加小模型", { exact: true })).toBeVisible();
  await expect(page.getByText("管理员功能", { exact: true })).toBeVisible();
  await expect(page.locator('input[type="file"][accept*=".zip"]')).toBeVisible();
  await expect(page.getByText(/model_card\.json.*config\.yaml.*inference\.py/)).toBeVisible();
  await expect(page.getByRole("button", { name: "上传并检查" })).toBeDisabled();
});
