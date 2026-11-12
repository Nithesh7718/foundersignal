import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOT_DIR = path.resolve(__dirname, "../test-results/screenshots");
const FIXTURES_DIR = path.resolve(__dirname, "fixtures");

test.describe("08 - Phase 2C Transcription, Audio Playback & Commitment Review", () => {
  let userToken: string;
  let workspaceId: string;

  test.beforeEach(async ({ page }) => {
    const rand = Math.floor(Math.random() * 100000);
    const testUser = {
      fullName: "Founder Reviewer",
      email: `founder_${Date.now()}_${rand}@testsignal.com`,
      password: "Password123!",
    };

    // Grant clipboard permissions for copy testing
    await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);

    // Register user
    await page.goto("/register", { waitUntil: "networkidle" });
    await page.fill("#full_name", testUser.fullName);
    await page.fill("#email", testUser.email);
    await page.fill("#password", testUser.password);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/conversations", { timeout: 15000 });

    userToken = (await page.evaluate(() => localStorage.getItem("foundersignal_token"))) || "";
    workspaceId = (await page.evaluate(() => localStorage.getItem("foundersignal_active_workspace"))) || "";
    expect(userToken).toBeTruthy();
    expect(workspaceId).toBeTruthy();
  });

  test("Audio playback: conversation detail page streams audio file and controls render", async ({
    page,
  }) => {
    // 1. Upload conversation with audio
    await page.goto("/conversations/new", { waitUntil: "networkidle" });
    await page.fill("#title", "Product Roadmap Review Voice Note");
    await page.setInputFiles("input[type='file']", path.join(FIXTURES_DIR, "valid_speech.wav"));
    await page.getByRole("button", { name: "Upload Audio" }).click();

    // 2. Redirects to conversations list, click card to view detail page
    await page.waitForURL("**/conversations", { timeout: 15000 });
    await page.locator("[data-testid^='conversation-card-']").first().click();
    await page.waitForURL(/\/conversations\/[0-9a-fA-F-]+$/, { timeout: 15000 });
    await expect(page.locator("[data-testid='conversation-title']")).toContainText(
      "Product Roadmap Review Voice Note"
    );

    // 3. Audio player card and controls render
    const audioCard = page.locator("[data-testid='audio-player-card']");
    await expect(audioCard).toBeVisible({ timeout: 10000 });
    await expect(audioCard).toContainText("valid_speech.wav");

    // Check play/pause button and scrubber
    const playBtn = page.locator("[data-testid='audio-play-pause-btn']");
    await expect(playBtn).toBeVisible();
    await expect(page.locator("[data-testid='audio-scrubber']")).toBeVisible();
    await expect(page.locator("[data-testid='audio-speed-btn']")).toBeVisible();
    await expect(page.locator("[data-testid='audio-mute-btn']")).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "phase2c_audio_player.png"),
      fullPage: true,
    });
  });

  test("Transcription trigger and progress pipeline: polls status until completed", async ({
    page,
  }) => {
    // 1. Upload conversation
    await page.goto("/conversations/new", { waitUntil: "networkidle" });
    await page.fill("#title", "Weekly Sprint Debrief");
    await page.setInputFiles("input[type='file']", path.join(FIXTURES_DIR, "valid_speech.wav"));
    await page.getByRole("button", { name: "Upload Audio" }).click();

    await page.waitForURL("**/conversations", { timeout: 15000 });
    await page.locator("[data-testid^='conversation-card-']").first().click();
    await page.waitForURL(/\/conversations\/[0-9a-fA-F-]+$/, { timeout: 15000 });

    // 2. Transcribe trigger card is visible
    const triggerCard = page.locator("[data-testid='transcription-trigger-card']");
    await expect(triggerCard).toBeVisible();
    await expect(page.locator("[data-testid='start-transcription-btn']")).toBeVisible();

    // 3. Click Transcribe Audio
    await page.locator("[data-testid='start-transcription-btn']").click();

    // 4. Progress or Active/Completed card appears
    await expect(
      page.locator("[data-testid='transcription-active-card'], [data-testid='transcription-completed-card']")
    ).toBeVisible({ timeout: 10000 });

    // 5. Wait for background worker to complete the job
    await expect(page.locator("[data-testid='transcription-completed-card']")).toBeVisible({
      timeout: 30000,
    });

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "phase2c_transcription_progress.png"),
      fullPage: true,
    });
  });

  test("Transcript display: renders verified transcript with metadata and copy action", async ({
    page,
    request,
  }) => {
    // 1. Create conversation via API
    const createRes = await request.post(`http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations`, {
      headers: { Authorization: `Bearer ${userToken}` },
      data: { title: "Strategy Session With Evidence", conversation_type: "meeting" },
    });
    const conv = await createRes.json();
    const convId = conv.id;

    // 2. Attach audio via API
    const fs = await import("fs");
    const wavBytes = fs.readFileSync(path.join(FIXTURES_DIR, "valid_speech.wav"));
    await request.post(`http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations/${convId}/audio`, {
      headers: { Authorization: `Bearer ${userToken}` },
      multipart: {
        file: {
          name: "valid_speech.wav",
          mimeType: "audio/wav",
          buffer: wavBytes,
        },
      },
    });

    // 3. Trigger transcription job via API
    const audioAssetId = (
      await (
        await request.get(`http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations/${convId}`, {
          headers: { Authorization: `Bearer ${userToken}` },
        })
      ).json()
    ).audio_assets[0].id;

    await request.post(
      `http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations/${convId}/transcribe`,
      {
        headers: { Authorization: `Bearer ${userToken}` },
        data: { audio_asset_id: audioAssetId, language_code: "indic-auto" },
      }
    );

    // 4. Open conversation detail page in browser
    await page.goto(`/conversations/${convId}`, { waitUntil: "networkidle" });

    // 5. Wait for completed transcript to display
    const transcriptCard = page.locator("[data-testid='transcript-card']");
    await expect(transcriptCard).toBeVisible({ timeout: 30000 });

    // Verify transcript elements
    await expect(
      page.locator("[data-testid='transcript-text'], [data-testid='transcript-empty-text']")
    ).toBeVisible();

    // Verify copy button
    const copyBtn = page.locator("[data-testid='copy-transcript-btn']");
    await expect(copyBtn).toBeVisible();
    await copyBtn.click();
    await expect(page.getByText("Copied")).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "phase2c_transcript_display.png"),
      fullPage: true,
    });
  });

  test("Commitment Review: founder reviews inferred commitments and confirms or rejects", async ({
    page,
    request,
  }) => {
    // 1. Create conversation with audio
    await page.goto("/conversations/new", { waitUntil: "networkidle" });
    await page.fill("#title", "Executive Decision Alignment");
    await page.setInputFiles("input[type='file']", path.join(FIXTURES_DIR, "valid_speech.wav"));
    await page.getByRole("button", { name: "Upload Audio" }).click();

    // Wait for redirect to conversations and click card to open details
    await page.waitForURL("**/conversations", { timeout: 15000 });
    await page.locator("[data-testid^='conversation-card-']").first().click();
    await page.waitForURL(/\/conversations\/[0-9a-fA-F-]+$/, { timeout: 15000 });
    const convUrl = page.url();
    const convId = convUrl.split("/").pop()!;

    // 2. Attach an inferred commitment with source quotation & confidence
    await request.post(`http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations/${convId}/commitments`, {
      headers: { Authorization: `Bearer ${userToken}` },
      data: {
        title: "Prepare onboarding flow before Thursday review",
        description: "Review and approve new founder onboarding milestone.",
        source_quote: "Let's ensure the onboarding flow is ready by Thursday before client review.",
        speaker: "Founder",
        confidence_score: 0.94,
        status: "inferred",
      },
    });

    // 3. Reload conversation to display the commitment
    await page.reload({ waitUntil: "networkidle" });

    // 4. Verify commitment card appears in "Pending Founder Review" status (Principle 4)
    const commitmentsList = page.locator("[data-testid='commitments-list']");
    await expect(commitmentsList).toBeVisible({ timeout: 10000 });

    const inferredBadge = page.locator("[data-testid='badge-inferred']").first();
    await expect(inferredBadge).toBeVisible();
    await expect(inferredBadge).toContainText("Pending Founder Review");

    // Check evidence source quote is present (Principle 1 & 3)
    const quote = page.locator("[data-testid='source-quote']").first();
    await expect(quote).toBeVisible();
    await expect(quote).toContainText("onboarding flow is ready by Thursday");

    // 5. Founder approves & confirms commitment (Principle 2: Human approval)
    const confirmBtn = page.locator("button[data-testid^='confirm-btn-']").first();
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    // Verify status transitions to "Confirmed Fact"
    const confirmedBadge = page.locator("[data-testid='badge-confirmed']").first();
    await expect(confirmedBadge).toBeVisible({ timeout: 5000 });
    await expect(confirmedBadge).toContainText("Confirmed Fact");

    // 6. Verify Filter tabs work
    await page.locator("[data-testid='filter-confirmed']").click();
    await expect(confirmedBadge).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "phase2c_commitment_approval.png"),
      fullPage: true,
    });
  });

  test("Conversation list navigation: clicking conversation card opens detail view", async ({
    page,
    request,
  }) => {
    // 1. Create a conversation
    const createRes = await request.post(`http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations`, {
      headers: { Authorization: `Bearer ${userToken}` },
      data: { title: "Clickable Card Test Conversation", conversation_type: "voice_note" },
    });
    const conv = await createRes.json();

    // 2. Go to conversation listing
    await page.goto("/conversations", { waitUntil: "networkidle" });

    // 3. Find card and click it
    const card = page.locator(`[data-testid='conversation-card-${conv.id}']`);
    await expect(card).toBeVisible();
    await card.click();

    // 4. Verify redirected to /conversations/[id]
    await page.waitForURL(`**/conversations/${conv.id}`, { timeout: 10000 });
    await expect(page.locator("[data-testid='conversation-title']")).toContainText(
      "Clickable Card Test Conversation"
    );
  });
});
