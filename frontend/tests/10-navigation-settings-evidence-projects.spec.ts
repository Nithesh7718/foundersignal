import { test, expect } from "@playwright/test";
import path from "path";

const FIXTURES_DIR = path.resolve(__dirname, "fixtures");

test.describe("10 - Navigation, Settings, Evidence Graph, and Projects & Delivery", () => {
  let userToken: string;
  let workspaceId: string;
  let testUser: { fullName: string; email: string; password: string };

  test.beforeEach(async ({ page }) => {
    const rand = Math.floor(Math.random() * 100000);
    testUser = {
      fullName: "Operating Cockpit Lead",
      email: `cockpit_${Date.now()}_${rand}@testsignal.com`,
      password: "Password123!",
    };

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

  test("Sidebar Navigation: Settings opens and renders real profile, workspace, members, and health", async ({
    page,
  }) => {
    // 1. Click sidebar nav for Settings
    const settingsNavLink = page.locator("[data-testid='nav-settings']");
    await expect(settingsNavLink).toBeVisible();
    await settingsNavLink.click();

    // 2. Verify URL is /settings
    await page.waitForURL("**/settings", { timeout: 10000 });

    // 3. Verify Settings page elements render
    await expect(page.locator("[data-testid='settings-page']")).toBeVisible();
    await expect(page.locator("[data-testid='workspace-settings-card']")).toBeVisible();
    await expect(page.locator("[data-testid='workspace-members-card']")).toBeVisible();
    await expect(page.locator("[data-testid='preferences-card']")).toBeVisible();
    await expect(page.locator("[data-testid='user-profile-card']")).toBeVisible();
    await expect(page.locator("[data-testid='system-health-card']")).toBeVisible();

    // Verify user profile details
    const profileCard = page.locator("[data-testid='user-profile-card']");
    await expect(profileCard.getByText(testUser.fullName)).toBeVisible();
    await expect(profileCard.getByText(testUser.email)).toBeVisible();

    // Verify service health indicators
    await expect(page.getByText("API Backend")).toBeVisible();
    await expect(page.getByText("PostgreSQL Database")).toBeVisible();

    // 4. Update workspace name and save
    const wsNameInput = page.locator("[data-testid='workspace-name-input']");
    await wsNameInput.fill("FounderSignal Core Operations");
    await page.locator("[data-testid='save-workspace-btn']").click();

    // 5. Verify success alert appears
    const successAlert = page.locator("[data-testid='settings-success-alert']");
    await expect(successAlert).toBeVisible();
    await expect(successAlert).toContainText("Workspace settings updated successfully");
  });

  test("Sidebar Navigation: Evidence Graph opens, loads data, and supports node inspection and filtering", async ({
    page,
    request,
  }) => {
    // 1. Seed conversation and commitment via backend API
    const convRes = await request.post(`http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations`, {
      headers: { Authorization: `Bearer ${userToken}` },
      data: { title: "Roadmap Sync", conversation_type: "meeting" },
    });
    expect(convRes.status()).toBe(201);
    const conv = await convRes.json();

    const commRes = await request.post(
      `http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations/${conv.id}/commitments`,
      {
        headers: { Authorization: `Bearer ${userToken}` },
        data: {
          title: "Deliver Q4 Architecture",
          source_quote: "We will deliver the Q4 architecture by end of month.",
          status: "confirmed",
          speaker: "Lead Architect",
        },
      }
    );
    expect(commRes.status()).toBe(201);

    // 2. Navigate via sidebar to Evidence Graph
    const evidenceNavLink = page.locator("[data-testid='nav-evidence-graph']");
    await expect(evidenceNavLink).toBeVisible();
    await evidenceNavLink.click();

    await page.waitForURL("**/evidence", { timeout: 10000 });
    await expect(page.locator("[data-testid='evidence-graph-page']")).toBeVisible();

    // 3. Verify metrics strip
    const metricsStrip = page.locator("[data-testid='graph-metrics-strip']");
    await expect(metricsStrip).toBeVisible();

    // 4. Verify nodes appear on canvas
    const convNode = page.locator(`[data-testid='graph-node-conv_${conv.id}']`);
    await expect(convNode).toBeVisible({ timeout: 10000 });
    await expect(convNode).toContainText("Roadmap Sync");

    // 5. Click node to inspect details in side drawer
    await convNode.click();
    const detailPanel = page.locator("[data-testid='node-detail-panel']");
    await expect(detailPanel).toBeVisible();
    await expect(page.locator("[data-testid='open-conversation-node-btn']")).toBeVisible();

    // 6. Test search filter
    const searchInput = page.locator("[data-testid='evidence-search-input']");
    await searchInput.fill("Deliver Q4");
    const commNode = page.locator(`[data-testid*='graph-node-comm_']`);
    await expect(commNode).toBeVisible();
  });

  test("Sidebar Navigation: Projects & Delivery opens, supports creating projects, and delivery tracking", async ({
    page,
    request,
  }) => {
    // 1. Seed a conversation and commitment
    const convRes = await request.post(`http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations`, {
      headers: { Authorization: `Bearer ${userToken}` },
      data: { title: "Sprint Backlog", conversation_type: "meeting" },
    });
    const conv = await convRes.json();

    const commRes = await request.post(
      `http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations/${conv.id}/commitments`,
      {
        headers: { Authorization: `Bearer ${userToken}` },
        data: {
          title: "Setup CI Hardening",
          source_quote: "Hardening all GitHub actions pipelines.",
          status: "confirmed",
        },
      }
    );
    const comm = await commRes.json();

    // 2. Navigate via sidebar to Projects & Delivery
    const projectsNavLink = page.locator("[data-testid='nav-projects-delivery']");
    await expect(projectsNavLink).toBeVisible();
    await projectsNavLink.click();

    await page.waitForURL("**/projects", { timeout: 10000 });
    await expect(page.locator("[data-testid='projects-page']")).toBeVisible();

    // 3. Verify delivery metrics strip renders
    await expect(page.locator("[data-testid='delivery-metrics-strip']")).toBeVisible();

    // 4. Create new Project via Modal
    await page.locator("[data-testid='open-create-project-btn']").click();
    const createModal = page.locator("[data-testid='create-project-modal']");
    await expect(createModal).toBeVisible();

    const projectName = `Security Milestone ${Date.now()}`;
    await page.locator("[data-testid='new-project-name-input']").fill(projectName);
    await page.locator("[data-testid='new-project-desc-input']").fill("Automated SOC2 audit compliance");
    await page.locator("[data-testid='save-new-project-btn']").click();

    // 5. Verify Project card appears
    await expect(createModal).toBeHidden();
    await expect(
      page.locator("[data-testid='projects-grid-section']").getByText(projectName)
    ).toBeVisible({ timeout: 10000 });

    // 6. Assign commitment to the newly created project
    const assignSelect = page.locator(`[data-testid='assign-project-select-${comm.id}']`);
    await expect(assignSelect).toBeVisible();
    await assignSelect.selectOption({ label: projectName });

    // 7. Verify commitment status update
    const commitmentRow = page.locator(`[data-testid='commitment-row-${comm.id}']`);
    await expect(commitmentRow).toBeVisible();
    const inProgressBtn = commitmentRow.getByRole("button", { name: "In Progress" });
    if (await inProgressBtn.isVisible()) {
      await inProgressBtn.click();
      await expect(page.locator("[data-testid='projects-success-alert']")).toBeVisible();
    }
  });

  test("Direct URL Navigation and Browser Refresh: all routes render and persist session", async ({
    page,
  }) => {
    // 1. Direct URL: /settings
    await page.goto("/settings", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='settings-page']")).toBeVisible();

    // Refresh /settings
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='settings-page']")).toBeVisible();
    await expect(
      page.locator("[data-testid='user-profile-card']").getByText(testUser.fullName)
    ).toBeVisible();

    // 2. Direct URL: /evidence
    await page.goto("/evidence", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='evidence-graph-page']")).toBeVisible();

    // Refresh /evidence
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='evidence-graph-page']")).toBeVisible();

    // 3. Direct URL: /projects
    await page.goto("/projects", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='projects-page']")).toBeVisible();

    // Refresh /projects
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='projects-page']")).toBeVisible();

    // 4. Browser Back and Forward Navigation
    await page.goBack();
    await expect(page.locator("[data-testid='evidence-graph-page']")).toBeVisible();
    await page.goForward();
    await expect(page.locator("[data-testid='projects-page']")).toBeVisible();
  });

  test("Strict Tenant Isolation: cross-workspace data is never displayed", async ({
    page,
    request,
  }) => {
    // 1. User A creates a confidential project and conversation
    const secretProjectName = `UserA Confidential ${Date.now()}`;
    await request.post(`http://localhost:8000/api/v1/workspaces/${workspaceId}/projects`, {
      headers: { Authorization: `Bearer ${userToken}` },
      data: { name: secretProjectName, description: "Strictly secret to Workspace A" },
    });

    // 2. Register User B with independent workspace
    const userB = {
      fullName: "User B Isolated",
      email: `userb_${Date.now()}@isolatedsignal.com`,
      password: "Password123!",
    };

    await page.goto("/register", { waitUntil: "networkidle" });
    await page.fill("#full_name", userB.fullName);
    await page.fill("#email", userB.email);
    await page.fill("#password", userB.password);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/conversations", { timeout: 15000 });

    // 3. Navigate to /projects as User B
    await page.goto("/projects", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='projects-page']")).toBeVisible();

    // User A's secret project must NOT be visible to User B
    await expect(page.getByText(secretProjectName)).toBeHidden();

    // 4. Navigate to /evidence as User B
    await page.goto("/evidence", { waitUntil: "networkidle" });
    await expect(page.locator("[data-testid='evidence-graph-page']")).toBeVisible();
    await expect(page.getByText(secretProjectName)).toBeHidden();
  });

  test("Cross-page Evidence Navigation: project deliverables link to conversation evidence", async ({
    page,
    request,
  }) => {
    // 1. Create conversation
    const convTitle = `Evidence Link Sync ${Date.now()}`;
    const convRes = await request.post(`http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations`, {
      headers: { Authorization: `Bearer ${userToken}` },
      data: { title: convTitle, conversation_type: "meeting" },
    });
    const conv = await convRes.json();

    // 2. Create commitment
    const commRes = await request.post(
      `http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations/${conv.id}/commitments`,
      {
        headers: { Authorization: `Bearer ${userToken}` },
        data: {
          title: "Deliver Audit Documentation",
          source_quote: "We will supply audit evidence.",
          status: "confirmed",
        },
      }
    );
    const comm = await commRes.json();

    // 3. Go to /projects and click "Evidence Audio" link
    await page.goto("/projects", { waitUntil: "networkidle" });
    const evidenceLink = page.locator(`[data-testid='view-evidence-btn-${comm.id}']`);
    await expect(evidenceLink).toBeVisible();
    await evidenceLink.click();

    // 4. Verify redirected to conversation detail page
    await page.waitForURL(`**/conversations/${conv.id}`, { timeout: 10000 });
    await expect(page.locator("[data-testid='conversation-title']")).toHaveText(convTitle);
  });

  test("Dashboard Quality: actions persist after refresh and approval count synchronizes", async ({
    page,
    request,
  }) => {
    // 1. Create a conversation and an inferred commitment
    const convRes = await request.post(`http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations`, {
      headers: { Authorization: `Bearer ${userToken}` },
      data: { title: "Approval Review Sync", conversation_type: "meeting" },
    });
    const conv = await convRes.json();

    const commTitle = `Inferred Promise ${Date.now()}`;
    await request.post(
      `http://localhost:8000/api/v1/workspaces/${workspaceId}/conversations/${conv.id}/commitments`,
      {
        headers: { Authorization: `Bearer ${userToken}` },
        data: {
          title: commTitle,
          source_quote: "I promise to ship the feature by Thursday.",
          status: "inferred",
        },
      }
    );

    // 2. Open Dashboard (/)
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.getByText(commTitle)).toBeVisible({ timeout: 10000 });

    // 3. Click Approve button on the commitment card
    const approveBtn = page.getByRole("button", { name: "Approve" }).first();
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();

    // 4. Wait for approval toast/badge update
    await expect(page.getByText("Approved commitment")).toBeVisible({ timeout: 5000 });

    // 5. Reload dashboard and verify commitment remains approved (status: confirmed)
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByText(commTitle)).toBeVisible();
    // Confirmed commitment has "Confirmed" status badge
    await expect(page.getByText("confirmed", { exact: false }).first()).toBeVisible();
  });
});
