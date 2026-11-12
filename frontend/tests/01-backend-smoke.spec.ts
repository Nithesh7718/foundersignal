import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOT_DIR = path.resolve(__dirname, "../test-results/screenshots");

test.describe("01 - Backend Smoke Tests", () => {
  const BACKEND_URL = "http://localhost:8000";

  test("GET /api/v1/health returns ready status and healthy database", async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/v1/health`);
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty("status", "ready");
    expect(data).toHaveProperty("service", "foundersignal-api");
    expect(data).toHaveProperty("version");
    expect(data).toHaveProperty("environment");
    expect(data).toHaveProperty("database_connected", true);
    expect(data).toHaveProperty("timestamp");
  });

  test("GET /api/v1/openapi.json returns valid OpenAPI specification", async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/v1/openapi.json`);
    expect(response.status()).toBe(200);

    const spec = await response.json();
    expect(spec.openapi).toMatch(/^3\./);
    expect(spec.info.title).toBe("FounderSignal API");
    expect(spec.paths).toHaveProperty("/api/v1/health");
    expect(spec.paths).toHaveProperty("/api/v1/auth/register");
    expect(spec.paths).toHaveProperty("/api/v1/auth/login");
    expect(spec.paths).toHaveProperty("/api/v1/workspaces");
  });

  test("GET /api/v1/docs loads Swagger UI without console errors", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    const response = await page.goto(`${BACKEND_URL}/api/v1/docs`, {
      waitUntil: "networkidle",
    });
    expect(response?.status()).toBe(200);

    // Wait for Swagger UI container to mount and display API title
    await expect(page.locator(".swagger-ui")).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("heading", { name: /FounderSignal API/i })).toBeVisible();

    // Screenshot Swagger UI
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "swagger_ui.png"),
      fullPage: true,
    });

    // Check for browser console errors
    expect(consoleErrors).toEqual([]);
  });
});
