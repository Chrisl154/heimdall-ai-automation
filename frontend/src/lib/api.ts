const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${path}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── PM ────────────────────────────────────────────────────────────────────────
export const api = {
  pm: {
    start: () => request("/api/pm/start", { method: "POST" }),
    stop: () => request("/api/pm/stop", { method: "POST" }),
    status: () => request<PMStatus>("/api/pm/status"),
    chat: (message: string, session_id = "default") =>
      request<{ reply: string; session_id: string }>("/api/pm/chat", {
        method: "POST",
        body: JSON.stringify({ message, session_id }),
      }),
  },

  tasks: {
    list: () => request<Task[]>("/api/tasks"),
    get: (id: string) => request<Task>(`/api/tasks/${id}`),
    create: (body: CreateTaskBody) =>
      request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Partial<Task>) =>
      request<Task>(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (id: string) => request(`/api/tasks/${id}`, { method: "DELETE" }),
  },

  vault: {
    keys: () => request<{ keys: string[] }>("/api/vault/keys"),
    has: (key: string) => request<{ key: string; exists: boolean }>(`/api/vault/has/${key}`),
    set: (key: string, value: string) =>
      request(`/api/vault/${key}`, { method: "PUT", body: JSON.stringify({ value }) }),
    delete: (key: string) => request(`/api/vault/${key}`, { method: "DELETE" }),
  },

  settings: {
    get: () => request<Record<string, unknown>>("/api/settings"),
    patch: (path: string, value: unknown) =>
      request("/api/settings", { method: "PATCH", body: JSON.stringify({ path, value }) }),
  },

  restrictions: {
    get: () => request<Record<string, unknown>>("/api/restrictions"),
    update: (yaml_content: string) =>
      request("/api/restrictions", { method: "PATCH", body: JSON.stringify({ yaml_content }) }),
  },

  messaging: {
    channels: () => request<MessagingChannel[]>("/api/messaging/channels"),
    addChannel: (body: unknown) =>
      request<MessagingChannel>("/api/messaging/channels", { method: "POST", body: JSON.stringify(body) }),
    updateChannel: (id: string, body: unknown) =>
      request<MessagingChannel>(`/api/messaging/channels/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    deleteChannel: (id: string) =>
      request(`/api/messaging/channels/${id}`, { method: "DELETE" }),
  },

  git: {
    status: () => request<GitStatus>("/api/git/status"),
    commits: (n = 10) => request<GitCommit[]>(`/api/git/commits?n=${n}`),
  },
};

// ── SSE ───────────────────────────────────────────────────────────────────────
export function subscribeToEvents(
  onEvent: (event: PipelineEvent) => void,
  onError?: (err: Event) => void
): () => void {
  const es = new EventSource(`${BASE}/api/pm/events`);
  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.type !== "ping") onEvent(data as PipelineEvent);
    } catch {}
  };
  if (onError) es.onerror = onError;
  return () => es.close();
}

// ── Types ─────────────────────────────────────────────────────────────────────
export type TaskStatus =
  | "pending" | "in_progress" | "in_review" | "fixing"
  | "completed" | "failed" | "escalated";

export interface Task {
  id: string;
  title: string;
  description: string;
  priority: "low" | "medium" | "high" | "critical";
  status: TaskStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  tags: string[];
  depends_on: string[];
  max_review_iterations: number;
  current_iteration: number;
  output_path: string;
  error?: string;
  latest_output?: string;
}

export interface CreateTaskBody {
  title: string;
  description: string;
  priority?: Task["priority"];
  tags?: string[];
  depends_on?: string[];
  max_review_iterations?: number;
  output_path?: string;
}

export interface PMStatus {
  running: boolean;
  current_task_id?: string;
  tasks_pending: number;
  tasks_completed: number;
  tasks_failed: number;
  tasks_escalated: number;
  uptime_seconds: number;
}

export interface PipelineEvent {
  type: string;
  task_id?: string;
  message: string;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface MessagingChannel {
  id: string;
  type: "telegram" | "discord" | "email";
  name: string;
  enabled: boolean;
  targets: string[];
}

export interface GitStatus {
  branch: string;
  clean: boolean;
  staged: string[];
  unstaged: string[];
}

export interface GitCommit {
  sha: string;
  message: string;
  author: string;
  date: string;
}
