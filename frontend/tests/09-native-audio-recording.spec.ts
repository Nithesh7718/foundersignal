import { test, expect } from "@playwright/test";
import path from "path";

const FIXTURES_DIR = path.resolve(__dirname, "fixtures");

test.describe("09 - Native Audio Recording & UX Enhancement", () => {
  let userToken: string;
  let workspaceId: string;

  test.beforeEach(async ({ page }) => {
    const rand = Math.floor(Math.random() * 100000);
    const testUser = {
      fullName: "Audio Recorder User",
      email: `recorder_${Date.now()}_${rand}@testsignal.com`,
      password: "Password123!",
    };

    // Grant permissions
    await page.context().grantPermissions(["microphone"]);

    // Register test user
    await page.goto("/register", { waitUntil: "networkidle" });
    await page.fill("#full_name", testUser.fullName);
    await page.fill("#email", testUser.email);
    await page.fill("#password", testUser.password);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/conversations", { timeout: 15000 });

    userToken = (await page.evaluate(() => localStorage.getItem("foundersignal_token"))) || "";
    workspaceId =
      (await page.evaluate(() => localStorage.getItem("foundersignal_active_workspace"))) || "";
    expect(userToken).toBeTruthy();
    expect(workspaceId).toBeTruthy();
  });

  test("UI Rendering: intake interface provides clearly visible Upload Audio | Record Audio tabs", async ({
    page,
  }) => {
    await page.goto("/conversations/new", { waitUntil: "networkidle" });

    // Both tabs should be present and visible
    const uploadTab = page.locator("[data-testid='tab-upload-audio']");
    const recordTab = page.locator("[data-testid='tab-record-audio']");
    await expect(uploadTab).toBeVisible();
    await expect(recordTab).toBeVisible();

    // Default tab is Upload Audio
    await expect(uploadTab).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("[data-testid='audio-upload-dropzone']")).toBeVisible();
    await expect(page.locator("[data-testid='audio-recorder-container']")).toBeHidden();

    // Switch to Record Audio tab
    await recordTab.click();
    await expect(recordTab).toHaveAttribute("aria-selected", "true");
    await expect(uploadTab).toHaveAttribute("aria-selected", "false");

    // Recorder container is now visible
    const recorder = page.locator("[data-testid='audio-recorder-container']");
    await expect(recorder).toBeVisible();

    // Status badge shows "Ready to record"
    const statusBadge = page.locator("[data-testid='recording-status-badge']");
    await expect(statusBadge).toHaveText("Ready to record");

    // Timer is at 00:00
    const timer = page.locator("[data-testid='recording-timer']");
    await expect(timer).toHaveText("00:00");

    // Big microphone record button is visible
    const startBtn = page.locator("[data-testid='start-recording-btn']");
    await expect(startBtn).toBeVisible();

    // Submit button is disabled because no audio recorded yet
    const submitBtn = page.locator("[data-testid='submit-audio-btn']");
    await expect(submitBtn).toBeDisabled();
    await expect(submitBtn).toHaveText("Submit for Transcription");
  });

  test("Error handling: microphone permission denied surfaces clear user alert", async ({
    page,
  }) => {
    await page.goto("/conversations/new", { waitUntil: "networkidle" });
    await page.locator("[data-testid='tab-record-audio']").click();

    // Mock getUserMedia to reject with NotAllowedError
    await page.evaluate(() => {
      navigator.mediaDevices.getUserMedia = () =>
        Promise.reject(new DOMException("Permission denied by user", "NotAllowedError"));
    });

    // Click start recording button
    await page.locator("[data-testid='start-recording-btn']").click();

    // Error banner should appear
    const alert = page.locator("[data-testid='recording-error-alert']");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("Microphone permission was denied");
    await expect(alert).toContainText("allow microphone access in your browser settings");

    // State remains ready to record
    await expect(page.locator("[data-testid='recording-status-badge']")).toHaveText("Ready to record");
    await expect(page.locator("[data-testid='start-recording-btn']")).toBeVisible();
  });

  test("Error handling: missing microphone device surfaces clear user alert", async ({
    page,
  }) => {
    await page.goto("/conversations/new", { waitUntil: "networkidle" });
    await page.locator("[data-testid='tab-record-audio']").click();

    // Mock getUserMedia to reject with NotFoundError
    await page.evaluate(() => {
      navigator.mediaDevices.getUserMedia = () =>
        Promise.reject(new DOMException("Requested device not found", "NotFoundError"));
    });

    // Click start recording button
    await page.locator("[data-testid='start-recording-btn']").click();

    // Error banner should appear
    const alert = page.locator("[data-testid='recording-error-alert']");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("No microphone was detected on your device");
  });

  test("Recording lifecycle: start, pause, resume, stop, preview, and re-record", async ({
    page,
  }) => {
    await page.goto("/conversations/new", { waitUntil: "networkidle" });
    await page.locator("[data-testid='tab-record-audio']").click();

    // 1. Start recording
    await page.locator("[data-testid='start-recording-btn']").click();

    // Badge indicates recording in progress
    const statusBadge = page.locator("[data-testid='recording-status-badge']");
    await expect(statusBadge).toHaveText("Recording audio", { timeout: 5000 });

    // Pause and Stop buttons become visible
    const pauseBtn = page.locator("[data-testid='pause-recording-btn']");
    const stopBtn = page.locator("[data-testid='stop-recording-btn']");
    await expect(pauseBtn).toBeVisible();
    await expect(stopBtn).toBeVisible();

    // Wait at least 1.5 seconds so timer increments
    await page.waitForTimeout(1600);
    const timer = page.locator("[data-testid='recording-timer']");
    const timerText = await timer.innerText();
    expect(timerText).not.toBe("00:00");

    // 2. Pause recording
    await pauseBtn.click();
    await expect(statusBadge).toHaveText("Recording paused");
    const resumeBtn = page.locator("[data-testid='resume-recording-btn']");
    await expect(resumeBtn).toBeVisible();

    // 3. Resume recording
    await resumeBtn.click();
    await expect(statusBadge).toHaveText("Recording audio");

    // 4. Stop recording
    await stopBtn.click();
    await expect(statusBadge).toHaveText("Recording ready", { timeout: 5000 });

    // 5. Audio preview player renders
    const previewPlayer = page.locator("[data-testid='audio-preview-player']");
    await expect(previewPlayer).toBeVisible();
    await expect(page.locator("[data-testid='audio-preview-play-btn']")).toBeVisible();
    await expect(page.locator("[data-testid='rerecord-btn']")).toBeVisible();
    const deleteBtn = page.locator("[data-testid='delete-recording-btn']");
    await expect(deleteBtn).toBeVisible();

    // Verify preview play toggle
    await page.locator("[data-testid='audio-preview-play-btn']").click();

    // 6. Delete recording
    await deleteBtn.click();
    await expect(statusBadge).toHaveText("Ready to record");
    await expect(timer).toHaveText("00:00");
    await expect(previewPlayer).toBeHidden();
    await expect(page.locator("[data-testid='start-recording-btn']")).toBeVisible();
  });

  test("End-to-End Submission: record audio, submit for transcription, and reuse pipeline", async ({
    page,
    request,
  }) => {
    await page.goto("/conversations/new", { waitUntil: "networkidle" });

    // Set Title and Type
    const testTitle = `Native Audio Recording Sync ${Date.now()}`;
    await page.fill("#title", testTitle);
    await page.selectOption("#type", "meeting");

    // Switch to record tab
    await page.locator("[data-testid='tab-record-audio']").click();

    // Record audio for ~2 seconds
    await page.locator("[data-testid='start-recording-btn']").click();
    await expect(page.locator("[data-testid='recording-status-badge']")).toHaveText(
      "Recording audio",
      { timeout: 5000 }
    );
    await page.waitForTimeout(2000);

    // Stop recording
    await page.locator("[data-testid='stop-recording-btn']").click();
    await expect(page.locator("[data-testid='recording-status-badge']")).toHaveText(
      "Recording ready",
      { timeout: 5000 }
    );

    // Submit button is now enabled
    const submitBtn = page.locator("[data-testid='submit-audio-btn']");
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Wait for redirect to conversations listing
    await page.waitForURL("**/conversations**", { timeout: 15000 });
    await expect(page.getByText(testTitle)).toBeVisible({ timeout: 10000 });

    // Verify via backend API that audio asset was saved with audio/webm
    const listRes = await request.get(
      `http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations`,
      {
        headers: { Authorization: `Bearer ${userToken}` },
      }
    );
    expect(listRes.status()).toBe(200);
    const conversations = await listRes.json();
    const createdConv = conversations.find((c: { title: string }) => c.title === testTitle);
    expect(createdConv).toBeTruthy();
    expect(createdConv.status).toBe("uploaded");
    expect(createdConv.audio_assets.length).toBe(1);

    const asset = createdConv.audio_assets[0];
    expect(asset.mime_type).toBe("audio/webm");
    expect(asset.file_name).toMatch(/^recording_\d+\.webm$/);
    expect(asset.file_size_bytes).toBeGreaterThan(0);

    // Open conversation detail page
    await page.goto(`/conversations/${createdConv.id}`, { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='conversation-title']")).toHaveText(testTitle);

    // Verify AudioPlayer renders with recorded webm file
    const audioCard = page.locator("[data-testid='audio-player-card']");
    await expect(audioCard).toBeVisible({ timeout: 10000 });
    await expect(audioCard).toContainText(".webm");

    // Verify TranscriptionStatus component renders and trigger transcription job
    const triggerCard = page.locator("[data-testid='transcription-trigger-card']");
    await expect(triggerCard).toBeVisible({ timeout: 10000 });
    const startTranscribeBtn = page.locator("[data-testid='start-transcription-btn']");
    await expect(startTranscribeBtn).toBeVisible();
    await startTranscribeBtn.click();

    // Transcription job pipeline starts and shows active or completed card
    await expect(
      page.locator(
        "[data-testid='transcription-active-card'], [data-testid='transcription-completed-card']"
      )
    ).toBeVisible({ timeout: 10000 });
  });

  test("Regression check: standard file upload remains completely operational", async ({
    page,
    request,
  }) => {
    await page.goto("/conversations/new", { waitUntil: "networkidle" });

    const title = `Standard WAV Upload Check ${Date.now()}`;
    await page.fill("#title", title);

    // Ensure we are on Upload Audio tab
    await page.locator("[data-testid='tab-upload-audio']").click();

    // Upload fixture file
    await page.setInputFiles("input[type='file']", path.join(FIXTURES_DIR, "valid_speech.wav"));
    await expect(page.getByText("valid_speech.wav")).toBeVisible();

    // Submit upload
    await page.getByRole("button", { name: "Upload Audio" }).click();

    // Wait for redirect
    await page.waitForURL("**/conversations**", { timeout: 15000 });
    await expect(page.getByText(title)).toBeVisible({ timeout: 10000 });

    // Verify database record
    const listRes = await request.get(
      `http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations`,
      {
        headers: { Authorization: `Bearer ${userToken}` },
      }
    );
    expect(listRes.status()).toBe(200);
    const conversations = await listRes.json();
    const createdConv = conversations.find((c: { title: string }) => c.title === title);
    expect(createdConv).toBeTruthy();
    expect(createdConv.audio_assets[0].mime_type).toBe("audio/wav");
    expect(createdConv.audio_assets[0].file_name).toBe("valid_speech.wav");
  });
});
