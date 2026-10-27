import { expect, type Page } from "@playwright/test";

// Needs the real API (local/test env, console SMS provider) for the dev OTP lookup.
export const API_URL = process.env.E2E_API_URL;

export function randomPhone(): string {
  return `+9198${Math.floor(10_000_000 + Math.random() * 89_999_999)}`;
}

export async function signIn(page: Page, phone: string): Promise<void> {
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

/** Give an account a role through the dev-only API, so a test can act as an admin. */
export async function grantRole(page: Page, phone: string, role: string): Promise<void> {
  const response = await page.request.post(`${API_URL}/api/v1/auth/_dev/grant-role`, {
    data: { phone, role },
  });
  expect(response.ok()).toBeTruthy();
}
