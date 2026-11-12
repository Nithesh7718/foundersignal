import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOT_DIR = path.resolve(__dirname, "../test-results/screenshots");
const FIXTURES_DIR = path.resolve(__dirname, "fixtures");

test.describe("04 - Workspace and Conversation Workflows", () => {
  test.beforeEach(async ({ page }) => {
    const rand = Math.floor(Math.random() * 100000);
    const testUser = {
      fullName: "Workspace E2E User",
      email: `ws_${Date.now()}_${rand}@testsignal.com`,
      password: "Password123!",
    };

    // Register unique user
    await page.goto("/register", { waitUntil: "networkidle" });
    await page.fill("#full_name", testUser.fullName);
    await page.fill("#email", testUser.email);
    await page.fill("#password", testUser.password);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/conversations", { timeout: 15000 });
  });

  test("Workspace indicator renders active workspace and supports multi-workspace switching", async ({
    page,
    request,
  }) => {
    // Check initial single workspace rendered as text in header
    await expect(page.getByText("Workspace E2E User's Workspace")).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "workspace_page.png"),
      fullPage: false,
    });

    // Extract access token from localStorage to invoke API
    const token = await page.evaluate(() => localStorage.getItem("foundersignal_token"));
    expect(token).toBeTruthy();

    // Create a second workspace via backend API
    const createWsRes = await request.post("http://localhost:8000/api/v1/workspaces", {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: "Secondary Ventures Workspace" },
    });
    expect(createWsRes.status()).toBe(201);

    // Reload page to allow auth-context to refresh workspaces list
    await page.reload({ waitUntil: "networkidle" });

    // The header should now render a select dropdown with both workspaces
    const wsSelect = page.locator("header select");
    await expect(wsSelect).toBeVisible();
    await expect(wsSelect).toContainText("Workspace E2E User's Workspace");
    await expect(wsSelect).toContainText("Secondary Ventures Workspace");

    // Switch to the second workspace
    const ws2Option = await wsSelect.locator("option", { hasText: "Secondary Ventures Workspace" }).getAttribute("value");
    if (ws2Option) {
      await wsSelect.selectOption(ws2Option);
    }
  });

  test("Conversation empty state renders correctly with prompt and call-to-action", async ({
    page,
  }) => {
    await page.goto("/conversations", { waitUntil: "networkidle" });
    await expect(page.getByText("No conversations recorded yet")).toBeVisible();
    await expect(
      page.getByText("Start by uploading an audio update or meeting recording to extract business commitments.")
    ).toBeVisible();

    const uploadCta = page.getByRole("link", { name: "Upload First Voice Update" });
    await expect(uploadCta).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "conversations_empty_state.png"),
      fullPage: true,
    });
  });

  test("Conversation creation form enforces validation for missing title and audio file", async ({
    page,
  }) => {
    await page.goto("/conversations/new", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Upload Conversation Audio" })).toBeVisible();

    const uploadBtn = page.getByRole("button", { name: "Upload Audio" });

    // Initially with both title and audio missing, submit button is disabled
    await expect(uploadBtn).toBeDisabled();

    // Fill title only (audio missing): submit button remains disabled
    await page.fill("#title", "Empty Audio Test");
    await expect(uploadBtn).toBeDisabled();

    // Clear title and provide audio only: submit button remains disabled
    await page.fill("#title", "");
    await page.setInputFiles("input[type='file']", path.join(FIXTURES_DIR, "valid_speech.wav"));
    await expect(uploadBtn).toBeDisabled();
  });

  test("Create conversation with valid audio and verify presence in conversation listing", async ({
    page,
  }) => {
    await page.goto("/conversations/new", { waitUntil: "networkidle" });

    // Fill title
    await page.fill("#title", "Quarterly Roadmap Review");

    // Select type "Team Meeting / Strategy Call"
    await page.selectOption("#type", "meeting");

    // Upload audio file using input[type='file']
    await page.setInputFiles("input[type='file']", path.join(FIXTURES_DIR, "valid_speech.wav"));

    // Verify selected file card displays
    await expect(page.getByText("valid_speech.wav")).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "audio_upload_interface_ready.png"),
      fullPage: true,
    });

    // Submit form
    const uploadBtn = page.getByRole("button", { name: "Upload Audio" });
    await expect(uploadBtn).toBeEnabled();
    await uploadBtn.click();

    // Verify redirect to conversations
    await page.waitForURL("**/conversations", { timeout: 15000 });

    // Verify conversation card is displayed
    await expect(page.getByText("Quarterly Roadmap Review")).toBeVisible();
    await expect(page.getByText("MEETING")).toBeVisible();
    await expect(page.getByText("1 Audio")).toBeVisible();
    await expect(page.getByText("0 Commitments")).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "conversation_page_with_items.png"),
      fullPage: true,
    });
  });
});
