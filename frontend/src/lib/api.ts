export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  role: string;
  created_at: string;
}

export interface AudioAsset {
  id: string;
  workspace_id: string;
  conversation_id: string;
  file_name: string;
  file_size_bytes: number;
  mime_type: string;
  duration_seconds?: number;
  status: string;
  created_at: string;
}

export interface Commitment {
  id: string;
  workspace_id: string;
  conversation_id: string;
  title: string;
  description?: string;
  status: string;
  confidence_score: number;
  source_quote: string;
  speaker?: string;
  timestamp_start?: number;
  timestamp_end?: number;
  assignee_id?: string;
  due_date?: string;
  created_at: string;
}

export interface Transcript {
  id: string;
  workspace_id: string;
  conversation_id: string;
  audio_asset_id?: string;
  provider: string;
  model?: string;
  language_code?: string;
  raw_transcript: string;
  status: string;
  confidence?: number;
  created_at: string;
}

export interface Conversation {
  id: string;
  workspace_id: string;
  title: string;
  conversation_type: string;
  status: string;
  recorded_at: string;
  created_at: string;
  audio_assets: AudioAsset[];
  commitments_count: number;
}

export interface ConversationDetail extends Conversation {
  transcripts: Transcript[];
  commitments: Commitment[];
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/v1\/?$/, "") ||
  "http://localhost:8000";

const TOKEN_KEY = "foundersignal_token";
const ACTIVE_WORKSPACE_KEY = "foundersignal_active_workspace";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ACTIVE_WORKSPACE_KEY);
}

export function getStoredWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_WORKSPACE_KEY);
}

export function setStoredWorkspaceId(id: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACTIVE_WORKSPACE_KEY, id);
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers: HeadersInit = {
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  // If not FormData, default to application/json
  if (!(options.body instanceof FormData)) {
    (headers as Record<string, string>)["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}/api/v1${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.error?.message) {
        errorMessage = errJson.error.message;
      } else if (errJson.detail) {
        errorMessage = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // Non-JSON response, fallback to status text
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Authentication
  async register(data: {
    email: string;
    password: string;
    full_name: string;
  }): Promise<AuthResponse> {
    const res = await request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
    setStoredToken(res.access_token);
    return res;
  },

  async login(data: { email: string; password: string }): Promise<AuthResponse> {
    const res = await request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
    setStoredToken(res.access_token);
    return res;
  },

  async logout(): Promise<void> {
    try {
      await request<{ message: string }>("/auth/logout", {
        method: "POST",
      });
    } finally {
      clearStoredToken();
    }
  },

  async getMe(): Promise<User> {
    return request<User>("/auth/me");
  },

  // Workspaces
  async listWorkspaces(): Promise<Workspace[]> {
    return request<Workspace[]>("/workspaces");
  },

  async createWorkspace(data: { name: string; slug?: string }): Promise<Workspace> {
    return request<Workspace>("/workspaces", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async getWorkspace(workspaceId: string): Promise<Workspace> {
    return request<Workspace>(`/workspaces/${workspaceId}`);
  },

  // Conversations
  async listConversations(workspaceId: string): Promise<Conversation[]> {
    return request<Conversation[]>(`/workspaces/${workspaceId}/conversations`);
  },

  async createConversation(
    workspaceId: string,
    data: { title: string; conversation_type?: string }
  ): Promise<Conversation> {
    return request<Conversation>(`/workspaces/${workspaceId}/conversations`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async getConversation(
    workspaceId: string,
    conversationId: string
  ): Promise<ConversationDetail> {
    return request<ConversationDetail>(
      `/workspaces/${workspaceId}/conversations/${conversationId}`
    );
  },

  async uploadAudio(
    workspaceId: string,
    conversationId: string,
    file: File
  ): Promise<AudioAsset> {
    const formData = new FormData();
    formData.append("file", file);

    return request<AudioAsset>(
      `/workspaces/${workspaceId}/conversations/${conversationId}/audio`,
      {
        method: "POST",
        body: formData,
      }
    );
  },
};
