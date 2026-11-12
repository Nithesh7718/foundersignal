import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOT_DIR = path.resolve(__dirname, "../test-results/screenshots");

test.describe("02 - Frontend Browser & Shell Tests", () => {
  test("Frontend loads with proper title, content, and zero uncaught JS exceptions", async ({ page }) => {
    const pageErrors: Error[] = [];
    const failedRequests: string[] = [];

    page.on("pageerror", (err) => pageErrors.push(err));
    page.on("requestfailed", (req) => {
      // Ignore aborts caused by navigation
      if (req.failure()?.errorText !== "net::ERR_ABORTED") {
        failedRequests.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText}`);
      }
    });

    await page.goto("/", { waitUntil: "networkidle" });

    // Page title and primary elements
    await expect(page).toHaveTitle(/FounderSignal/i);
    await expect(page.getByText("FounderSignal Operating Cockpit")).toBeVisible();
    await expect(page.getByText("Founder Cockpit")).toBeVisible();

    // Verify API Connected status badge is rendered on desktop header
    await expect(page.locator("header").getByText("API Connected")).toBeVisible({ timeout: 10000 });

    // Capture desktop screenshot
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "landing_page_desktop.png"),
      fullPage: true,
    });

    // Check no uncaught JS exceptions and no unexpected failed requests
    expect(pageErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("Navigation links between Dashboard and Conversations work seamlessly", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });

    // Click "View Conversations" button in welcome banner
    await page.getByRole("link", { name: "View Conversations" }).click();
    await page.waitForURL("**/conversations");
    await expect(page.getByRole("heading", { name: "Sign in to view conversations" })).toBeVisible();

    // Click "Dashboard" in sidebar
    await page.getByRole("link", { name: "Dashboard" }).click();
    await page.waitForURL("**/");
    await expect(page.getByText("FounderSignal Operating Cockpit")).toBeVisible();
  });

  test("Responsive layout: desktop and mobile viewports render cleanly without horizontal overflow", async ({
    page,
  }) => {
    // Desktop Viewport Test (1280x800)
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

    const isDesktopOverflowing = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(isDesktopOverflowing).toBe(false);

    // Sidebar should be visible on desktop
    const sidebar = page.locator("aside");
    await expect(sidebar).toBeVisible();

    // Mobile Viewport Test (375x667)
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/", { waitUntil: "networkidle" });

    const isMobileOverflowing = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(isMobileOverflowing).toBe(false);

    // Desktop sidebar should be hidden on mobile
    await expect(sidebar).toBeHidden();

    // Mobile hamburger menu button should be visible
    const hamburgerBtn = page.getByRole("button", { name: "Open navigation menu" });
    await expect(hamburgerBtn).toBeVisible();

    // Open mobile menu
    await hamburgerBtn.click();
    await expect(page.getByRole("button", { name: "Close navigation menu" })).toBeVisible();

    // Capture mobile screenshot
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "landing_page_mobile.png"),
      fullPage: true,
    });
  });
});
