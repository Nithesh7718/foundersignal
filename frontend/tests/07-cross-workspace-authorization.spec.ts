import { test, expect } from "@playwright/test";

test.describe("07 - Cross-Workspace Authorization & Tenant Isolation", () => {
  const userA = {
    fullName: "Alice Founder A",
    email: `alice_${Date.now()}_${Math.floor(Math.random() * 10000)}@testsignal.com`,
    password: "Password123!",
  };

  const userB = {
    fullName: "Bob Competitor B",
    email: `bob_${Date.now()}_${Math.floor(Math.random() * 10000)}@testsignal.com`,
    password: "Password123!",
  };

  let tokenA: string;
  let workspaceAId: string;
  let conversationAId: string;
  let tokenB: string;
  let workspaceBId: string;
  let workspaceBName: string;

  test.beforeAll(async ({ request }) => {
    // 1. Register User A
    const regARes = await request.post("http://localhost:8000/api/v1/auth/register", {
      data: {
        email: userA.email,
        password: userA.password,
        full_name: userA.fullName,
      },
    });
    expect(regARes.status()).toBe(201);
    const dataA = await regARes.json();
    tokenA = dataA.access_token;

    // Get User A's default workspace
    const wsListARes = await request.get("http://localhost:8000/api/v1/workspaces", {
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    expect(wsListARes.status()).toBe(200);
    const wsListA = await wsListARes.json();
    workspaceAId = wsListA[0].id;

    // Create a confidential conversation in Workspace A
    const convARes = await request.post(
      `http://localhost:8000/api/v1/workspaces/${workspaceAId}/conversations`,
      {
        headers: { Authorization: `Bearer ${tokenA}` },
        data: {
          title: "Alice Confidential Strategy 2027",
          conversation_type: "board_sync",
        },
      }
    );
    expect(convARes.status()).toBe(201);
    const convA = await convARes.json();
    conversationAId = convA.id;

    // 2. Register User B (separate organization / competitor)
    const regBRes = await request.post("http://localhost:8000/api/v1/auth/register", {
      data: {
        email: userB.email,
        password: userB.password,
        full_name: userB.fullName,
      },
    });
    expect(regBRes.status()).toBe(201);
    const dataB = await regBRes.json();
    tokenB = dataB.access_token;

    const wsListBRes = await request.get("http://localhost:8000/api/v1/workspaces", {
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    expect(wsListBRes.status()).toBe(200);
    const wsListB = await wsListBRes.json();
    workspaceBId = wsListB[0].id;
    workspaceBName = wsListB[0].name;
  });

  test("User B is strictly forbidden (HTTP 403 ACCESS_DENIED) from reading Workspace A details", async ({
    request,
  }) => {
    const res = await request.get(`http://localhost:8000/api/v1/workspaces/${workspaceAId}`, {
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    expect(res.status()).toBe(403);
    const body = await res.json();
    expect(body.error.code).toBe("ACCESS_DENIED");
    expect(body.error.message).toContain("You do not have access to this workspace");
  });

  test("User B is strictly forbidden (HTTP 403 ACCESS_DENIED) from listing Workspace A conversations", async ({
    request,
  }) => {
    const res = await request.get(
      `http://localhost:8000/api/v1/workspaces/${workspaceAId}/conversations`,
      {
        headers: { Authorization: `Bearer ${tokenB}` },
      }
    );
    expect(res.status()).toBe(403);
    const body = await res.json();
    expect(body.error.code).toBe("ACCESS_DENIED");
    expect(body.error.message).toContain("You do not have access to this workspace");
  });

  test("User B cannot access or inspect confidential conversations belonging to Workspace A", async ({
    request,
  }) => {
    const res = await request.get(
      `http://localhost:8000/api/v1/workspaces/${workspaceAId}/conversations/${conversationAId}`,
      {
        headers: { Authorization: `Bearer ${tokenB}` },
      }
    );
    expect(res.status()).toBe(403);
    const body = await res.json();
    expect(body.error.code).toBe("ACCESS_DENIED");
  });

  test("User B cannot create a conversation under Workspace A", async ({ request }) => {
    const res = await request.post(
      `http://localhost:8000/api/v1/workspaces/${workspaceAId}/conversations`,
      {
        headers: { Authorization: `Bearer ${tokenB}` },
        data: {
          title: "Malicious Injected Conversation",
          conversation_type: "meeting",
        },
      }
    );
    expect(res.status()).toBe(403);
    const body = await res.json();
    expect(body.error.code).toBe("ACCESS_DENIED");
  });

  test("User B cannot delete conversations belonging to Workspace A", async ({ request }) => {
    const res = await request.delete(
      `http://localhost:8000/api/v1/workspaces/${workspaceAId}/conversations/${conversationAId}`,
      {
        headers: { Authorization: `Bearer ${tokenB}` },
      }
    );
    expect(res.status()).toBe(403);

    // Verify conversation still exists untouched for User A
    const verifyRes = await request.get(
      `http://localhost:8000/api/v1/workspaces/${workspaceAId}/conversations/${conversationAId}`,
      {
        headers: { Authorization: `Bearer ${tokenA}` },
      }
    );
    expect(verifyRes.status()).toBe(200);
  });

  test("Client state tampering: unauthorized workspace injection is safely sanitized and blocked", async ({
    page,
  }) => {
    // Log in as User B
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.fill("#email", userB.email);
    await page.fill("#password", userB.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/conversations");

    // Tamper with active workspace in localStorage by injecting Workspace A ID
    await page.evaluate((targetWsId) => {
      localStorage.setItem("foundersignal_active_workspace", targetWsId);
    }, workspaceAId);

    // Reload conversations page
    await page.reload({ waitUntil: "networkidle" });

    // Client AuthProvider sanitizes foreign workspace ID and resets to User B's workspace
    await expect(page.getByText(workspaceBName)).toBeVisible();

    // Verify Alice's confidential conversation from Workspace A is strictly inaccessible
    await expect(page.getByText("Alice Confidential Strategy 2027")).toBeHidden();
  });
});
