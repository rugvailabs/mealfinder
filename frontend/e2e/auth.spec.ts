import { expect, test, type Page } from "@playwright/test";

// Needs the real API (local/test env, console SMS provider) for the dev OTP lookup.
const API_URL = process.env.E2E_API_URL;
test.skip(!API_URL, "set E2E_API_URL to run sign-in tests against a running stack");

function randomPhone(): string {
  return `+9198${Math.floor(10_000_000 + Math.random() * 89_999_999)}`;
}

async function signIn(page: Page, phone: string): Promise<void> {
  await page.getByLabel("Mobile number").fill(phone);
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(page.getByText(`We sent a code to ${phone}`)).toBeVisible();

  const response = await page.request.get(`${API_URL}/api/v1/auth/_dev/last-otp`, {
    params: { phone },
  });
  expect(response.ok()).toBeTruthy();
  const { code } = (await response.json()) as { code: string };

  await page.getByLabel("Code").fill(code);
  await page.getByRole("button", { name: "Verify" }).click();
}

test("sign in by SMS code, survive a reload, then sign out", async ({ page }) => {
  const phone = randomPhone();

  await page.goto("/login");
  await signIn(page, phone);

  // A new number becomes a customer and lands on the customer home.
  await expect(page).toHaveURL("/");
  await expect(page.getByTestId("signed-in-phone")).toHaveText(phone);

  // The access token is in memory only; the refresh cookie restores the session.
  await page.reload();
  await expect(page.getByTestId("signed-in-phone")).toHaveText(phone);

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
});

test("a customer is sent back to the portal they asked for, and told it isn't theirs", async ({
  page,
}) => {
  await page.goto("/cook");
  await expect(page).toHaveURL("/login?next=%2Fcook");
  await signIn(page, randomPhone());

  await expect(page).toHaveURL("/cook");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "You don't have access to this page",
  );
});

test("a wrong code shows an error", async ({ page }) => {
  const phone = randomPhone();
  await page.goto("/login");
  await page.getByLabel("Mobile number").fill(phone);
  await page.getByRole("button", { name: "Send code" }).click();
  await page.getByLabel("Code").fill("000000");
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByRole("alert")).toHaveText("That code is invalid or has expired");
});
