import { expect, test } from "@playwright/test";

test("customer home renders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("home-cooked meal");
});

for (const [path, heading] of [
  ["/cook", "Cook dashboard"],
  ["/agent", "Deliveries"],
  ["/shop", "Shop stock"],
  ["/admin", "Admin overview"],
]) {
  test(`${path} portal renders`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading);
  });
}
