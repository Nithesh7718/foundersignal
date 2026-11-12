import { test, expect } from "@playwright/test";

test.describe("06 - API Integration & Security", () => {
  const rand = Math.floor(Math.random() * 100000);
  const testUser = {
    fullName: "Security Audit User",
    email: `sec_${Date.now()}_${rand}@testsignal.com`,
    password: "Password123!",
  };

  test("Browser requests use correct backend base URL and send Authorization Bearer headers", async ({
    page,
  }) => {
    const apiRequests: { url: string; authHeader?: string }[] = [];

    // Monitor network requests
    page.on("request", (req) => {
      const url = req.url();
      if (url.includes("/api/v1/")) {
        apiRequests.push({
          url,
          authHeader: req.headers()["authorization"],
        });
      }
    });

    // Register user
    await page.goto("/register", { waitUntil: "networkidle" });
    await page.fill("#full_name", testUser.fullName);
    await page.fill("#email", testUser.email);
    await page.fill("#password", testUser.password);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/conversations", { timeout: 15000 });

    // Verify all captured API requests targeted http://localhost:8000/api/v1/
    expect(apiRequests.length).toBeGreaterThan(0);
    for (const req of apiRequests) {
      expect(req.url).toContain("http://localhost:8000/api/v1/");
    }

    // Verify authenticated requests carried Authorization Bearer token
    const authenticatedRequests = apiRequests.filter(
      (r) => r.url.includes("/workspaces") || r.url.includes("/auth/me")
    );
    expect(authenticatedRequests.length).toBeGreaterThan(0);
    for (const authReq of authenticatedRequests) {
      expect(authReq.authHeader).toBeDefined();
      expect(authReq.authHeader).toMatch(/^Bearer\s+ey/);
    }
  });

  test("Credential privacy: no passwords or secret tokens leaked into console logs", async ({
    page,
  }) => {
    const consoleLogs: string[] = [];
    page.on("console", (msg) => {
      consoleLogs.push(msg.text());
    });

    await page.goto("/login", { waitUntil: "networkidle" });
    await page.fill("#email", testUser.email);
    await page.fill("#password", testUser.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/conversations", { timeout: 15000 });

    // Inspect all captured console logs for testUser.password
    for (const logText of consoleLogs) {
      expect(logText).not.toContain(testUser.password);
      expect(logText).not.toContain("foundersignal_secret");
    }
  });

  test("CORS verification: backend responses allow frontend origin without browser blocking", async ({
    page,
    request,
  }) => {
    // Check CORS preflight response headers from backend
    const optionsRes = await request.fetch("http://localhost:8000/api/v1/health", {
      method: "OPTIONS",
      headers: {
        Origin: "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
      },
    });
    expect([200, 204]).toContain(optionsRes.status());
    const corsHeader = optionsRes.headers()["access-control-allow-origin"];
    expect(corsHeader === "http://localhost:3000" || corsHeader === "*").toBe(true);

    // In-browser navigation should have zero CORS errors
    const corsErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.text().toLowerCase().includes("cors")) {
        corsErrors.push(msg.text());
      }
    });

    await page.goto("/", { waitUntil: "networkidle" });
    expect(corsErrors).toEqual([]);
  });
});
