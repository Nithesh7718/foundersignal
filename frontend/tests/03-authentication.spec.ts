import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOT_DIR = path.resolve(__dirname, "../test-results/screenshots");

function getUniqueUser(prefix = "user") {
  const rand = Math.floor(Math.random() * 100000);
  return {
    fullName: "E2E Test Founder",
    email: `${prefix}_${Date.now()}_${rand}@testsignal.com`,
    password: "Password123!",
  };
}

test.describe("03 - Authentication Workflows", () => {
  test("Registration form validation: rejects short password & enforces required fields", async ({
    page,
  }) => {
    const dummyUser = getUniqueUser("val");
    await page.goto("/register", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "registration_page.png"),
      fullPage: true,
    });

    // Fill short password (< 8 chars)
    await page.fill("#full_name", dummyUser.fullName);
    await page.fill("#email", dummyUser.email);
    await page.fill("#password", "short");
    await page.getByRole("button", { name: "Create account" }).click();

    // Verify client validation error
    const errorAlert = page.locator("form [role='alert']");
    await expect(errorAlert).toBeVisible();
    await expect(errorAlert).toContainText("Password must be at least 8 characters long.");
  });

  test("Registration form validation: surfaces detailed field validation errors from backend", async ({
    page,
  }) => {
    await page.goto("/register", { waitUntil: "networkidle" });
    await page.fill("#full_name", "Invalid Domain Test");
    await page.fill("#email", "founder@test.local");
    await page.fill("#password", "ValidPass123!");
    await page.getByRole("button", { name: "Create account" }).click();

    // Verify backend field-level validation message is surfaced directly to user
    const errorAlert = page.locator("form [role='alert']");
    await expect(errorAlert).toBeVisible();
    await expect(errorAlert).toContainText("email:");
  });

  test("Successful user registration creates user and initializes default workspace", async ({
    page,
  }) => {
    const regUser = getUniqueUser("reg");
    await page.goto("/register", { waitUntil: "networkidle" });

    // Fill valid registration fields
    await page.fill("#full_name", regUser.fullName);
    await page.fill("#email", regUser.email);
    await page.fill("#password", regUser.password);

    await page.getByRole("button", { name: "Create account" }).click();

    // Redirection to conversations
    await page.waitForURL("**/conversations", { timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Conversations & Audio" })).toBeVisible();

    // Header displays user initials "ET" (exact match to avoid matching substring in Settings/Yet)
    await expect(page.getByText("ET", { exact: true })).toBeVisible();
    await expect(page.getByText(regUser.email)).toBeVisible();
    await expect(page.getByText("E2E Test Founder's Workspace")).toBeVisible();

    // Screenshot authenticated conversations page
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "authenticated_conversations_empty.png"),
      fullPage: true,
    });
  });

  test("Session persistence: user session survives page reload", async ({ page }) => {
    const sessUser = getUniqueUser("sess");
    await page.goto("/register", { waitUntil: "networkidle" });
    await page.fill("#full_name", sessUser.fullName);
    await page.fill("#email", sessUser.email);
    await page.fill("#password", sessUser.password);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/conversations", { timeout: 15000 });

    await expect(page.getByText(sessUser.email)).toBeVisible();

    // Reload page
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByText(sessUser.email)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Conversations & Audio" })).toBeVisible();
  });

  test("Logout revokes token and clears client state", async ({ page }) => {
    const logoutUser = getUniqueUser("logout");
    await page.goto("/register", { waitUntil: "networkidle" });
    await page.fill("#full_name", logoutUser.fullName);
    await page.fill("#email", logoutUser.email);
    await page.fill("#password", logoutUser.password);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/conversations", { timeout: 15000 });

    await expect(page.getByText(logoutUser.email)).toBeVisible();

    // Click logout button (Sign out icon)
    const logoutBtn = page.getByRole("button", { name: "Sign out" });
    await expect(logoutBtn).toBeVisible();
    await logoutBtn.click();

    // Header should now show Sign In / Sign Up buttons
    await expect(page.locator("header").getByRole("link", { name: "Sign In" })).toBeVisible();
    await expect(page.locator("header").getByRole("link", { name: "Sign Up" })).toBeVisible();

    // Verify localStorage tokens are cleared
    const token = await page.evaluate(() => localStorage.getItem("foundersignal_token"));
    expect(token).toBeNull();
  });

  test("Protected routes display sign-in prompt when unauthenticated", async ({ page }) => {
    // Clear storage to ensure guest state
    await page.goto("/", { waitUntil: "networkidle" });
    await page.evaluate(() => localStorage.clear());

    // Access /conversations
    await page.goto("/conversations", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Sign in to view conversations" })).toBeVisible();

    // Access /conversations/new
    await page.goto("/conversations/new", { waitUntil: "networkidle" });
    await expect(page.getByText("Please sign in to record or upload audio.")).toBeVisible();
  });

  test("Login with invalid credentials displays error message", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "login_page.png"),
      fullPage: true,
    });

    await page.fill("#email", "nonexistent_founder@testsignal.com");
    await page.fill("#password", "WrongPassword123!");
    await page.getByRole("button", { name: "Sign in" }).click();

    const errorAlert = page.locator("form [role='alert']");
    await expect(errorAlert).toBeVisible();
    await expect(errorAlert).toContainText(/invalid/i);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "login_error.png"),
      fullPage: true,
    });
  });

  test("Login with valid credentials succeeds and navigates to conversations", async ({
    page,
    request,
  }) => {
    const loginUser = getUniqueUser("login");

    // Register user via API first to guarantee existence
    const regRes = await request.post("http://localhost:8000/api/v1/auth/register", {
      data: {
        email: loginUser.email,
        password: loginUser.password,
        full_name: loginUser.fullName,
      },
    });
    expect(regRes.status()).toBe(201);

    // Now log in via the UI
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.fill("#email", loginUser.email);
    await page.fill("#password", loginUser.password);
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("**/conversations", { timeout: 15000 });
    await expect(page.getByText(loginUser.email)).toBeVisible();

    // Navigate to Dashboard
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.getByText("FounderSignal Operating Cockpit")).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "main_authenticated_dashboard.png"),
      fullPage: true,
    });
  });
});
