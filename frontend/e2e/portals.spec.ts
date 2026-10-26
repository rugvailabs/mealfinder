import { expect, test } from "@playwright/test";

test("customer home is public", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("home-cooked meal");
  await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
});

for (const path of ["/cook", "/agent", "/shop", "/admin"]) {
  test(`${path} sends signed-out visitors to sign in`, async ({ page }) => {
    await page.goto(path);
    await expect(page).toHaveURL(`/login?next=${encodeURIComponent(path)}`);
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });
}
