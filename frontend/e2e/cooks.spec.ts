import { expect, test, type Page } from "@playwright/test";

import { API_URL, grantRole, randomPhone, signIn } from "./support";

test.skip(!API_URL, "set E2E_API_URL to run cook onboarding tests against a running stack");

async function cookStatus(page: Page) {
  await page.goto("/cook/profile");
  return page.getByTestId("approval-status");
}

async function adminRow(page: Page, tab: string, kitchen: string) {
  await page.goto("/admin/cooks");
  await page.getByRole("tab", { name: tab }).click();
  const row = page.getByRole("listitem", { name: kitchen });
  await expect(row).toBeVisible();
  return row;
}

test("a cook applies, is rejected, resubmits and is approved", async ({ browser }) => {
  const kitchen = `Kitchen ${Date.now()}`;

  // The cook applies from the customer site.
  const cook = await (await browser.newContext()).newPage();
  await cook.goto("/become-a-cook");
  await expect(cook).toHaveURL("/login?next=%2Fbecome-a-cook");
  await signIn(cook, randomPhone());
  await expect(cook).toHaveURL("/become-a-cook");
  await cook.getByLabel("Kitchen name").fill(kitchen);
  await cook.getByLabel("About your cooking (optional)").fill("Andhra home meals");
  await cook.getByRole("button", { name: "Apply" }).click();

  await expect(cook).toHaveURL("/cook/profile");
  await expect(cook.getByTestId("approval-status")).toHaveText("pending");

  const address = cook.getByRole("form", { name: "Home address" });
  await address.getByLabel("Address line 1").fill("12 Temple Street");
  await address.getByLabel("City").fill("Hyderabad");
  await address.getByLabel("Pincode").fill("500001");
  await address.getByLabel("Latitude").fill("17.385");
  await address.getByLabel("Longitude").fill("78.4867");
  await address.getByRole("button", { name: "Save address" }).click();
  await expect(cook.getByRole("status")).toHaveText("Address saved");

  // Editing the profile keeps the status.
  await cook.getByLabel("About your cooking").fill("Andhra and Telangana home meals");
  await cook.getByRole("button", { name: "Save profile" }).click();
  await expect(cook.getByRole("status")).toHaveText("Profile saved");
  await cook.reload();
  await expect(cook.getByTestId("approval-status")).toHaveText("pending");
  await expect(cook.getByLabel("Address line 1")).toHaveValue("12 Temple Street");

  // An admin rejects with a reason.
  const adminPhone = randomPhone();
  const admin = await (await browser.newContext()).newPage();
  await grantRole(admin, adminPhone, "admin");
  await admin.goto("/login?next=%2Fadmin%2Fcooks");
  await signIn(admin, adminPhone);
  await expect(admin).toHaveURL("/admin/cooks");

  let row = await adminRow(admin, "Pending", kitchen);
  await expect(row.getByText("address on file")).toBeVisible();
  // The admin list never shows the address itself.
  await expect(row.getByText("Temple Street")).toHaveCount(0);
  await row.getByRole("button", { name: "Reject" }).click();
  await row.getByLabel("Reason to reject").fill("Please add a kitchen description");
  await row.getByRole("button", { name: "Confirm reject" }).click();
  await expect(row).toHaveCount(0); // gone from the pending tab

  // The cook sees why, and resubmits.
  await expect(await cookStatus(cook)).toHaveText("rejected");
  await expect(cook.getByText("Reason: Please add a kitchen description")).toBeVisible();
  await cook.getByRole("button", { name: "Resubmit for review" }).click();
  await expect(cook.getByTestId("approval-status")).toHaveText("pending");

  // The admin still sees the earlier rejection, and approves.
  row = await adminRow(admin, "Pending", kitchen);
  await expect(
    row.getByText("Previously rejected: Please add a kitchen description"),
  ).toBeVisible();
  await row.getByRole("button", { name: "Approve" }).click();
  await expect(row).toHaveCount(0);

  row = await adminRow(admin, "Approved", kitchen);
  await expect(row.getByTestId("cook-status")).toHaveText("approved");
  await expect(await cookStatus(cook)).toHaveText("approved");

  // Suspend, then reinstate.
  await row.getByRole("button", { name: "Suspend" }).click();
  await row.getByLabel("Reason to suspend").fill("Hygiene complaint");
  await row.getByRole("button", { name: "Confirm suspend" }).click();
  await expect(await cookStatus(cook)).toHaveText("suspended");
  row = await adminRow(admin, "Suspended", kitchen);
  await row.getByRole("button", { name: "Reinstate" }).click();
  await expect(await cookStatus(cook)).toHaveText("approved");
});

test("a pending cook can't be approved before adding an address", async ({ browser }) => {
  const kitchen = `No Address ${Date.now()}`;
  const cook = await (await browser.newContext()).newPage();
  await cook.goto("/login?next=%2Fbecome-a-cook");
  await signIn(cook, randomPhone());
  await cook.getByLabel("Kitchen name").fill(kitchen);
  await cook.getByRole("button", { name: "Apply" }).click();
  await expect(cook.getByTestId("approval-status")).toHaveText("pending");

  const adminPhone = randomPhone();
  const admin = await (await browser.newContext()).newPage();
  await grantRole(admin, adminPhone, "admin");
  await admin.goto("/login?next=%2Fadmin%2Fcooks");
  await signIn(admin, adminPhone);
  const row = await adminRow(admin, "Pending", kitchen);
  await expect(row.getByText("no address yet")).toBeVisible();
  await expect(row.getByRole("button", { name: "Approve" })).toBeDisabled();
});
