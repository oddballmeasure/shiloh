import { expect, test } from "@playwright/test";

import { ADMIN_STATE_PATH } from "./auth-files";

test.use({ storageState: ADMIN_STATE_PATH });

test("admin pages expose seeded users and moderated content", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Admin Panel" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Users" })).toBeVisible();

  await page.goto("/admin/users");
  const learnerCard = page.locator("article").filter({ hasText: "Learner" });
  await expect(learnerCard).toBeVisible();
  await learnerCard.getByRole("link", { name: "Inspect" }).click();
  await expect(page.getByText("Discord ID: discord-learner")).toBeVisible();
  await expect(page.getByText("Current Discord Profile")).toBeVisible();
  await expect(page.getByRole("button", { name: "Deactivate User" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Promote To Admin" })).toBeVisible();

  await page.goto("/admin/flashcard-sets");
  await expect(page.getByText("Seeded Travel Set")).toBeVisible();
  await expect(page.getByRole("button", { name: "Delete Set" }).first()).toBeVisible();

  await page.goto("/admin/assignments");
  await expect(page.getByText("Seeded PDF Assignment")).toBeVisible();
  await expect(page.getByRole("link", { name: "View Submitted PDF" }).first()).toBeVisible();
});

test.use({ storageState: ADMIN_STATE_PATH, viewport: { width: 375, height: 812 } });

test("mobile navigation exposes admin links", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Menu" }).click();
  await expect(page.getByRole("link", { name: "Admin", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Admin", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Admin Panel" })).toBeVisible();
});
