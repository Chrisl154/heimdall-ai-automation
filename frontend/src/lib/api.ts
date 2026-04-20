const BASE = process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined"
    ? `http://${window.location.hostname}:8000`
    : "http://localhost:8000");

const getToken = () => (typeof window !== "undefined" ? localStorage.getItem("heimdall_token") ?? "" : "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
       "Content-Type": "application/json",
       ...(getToken() ? { "Authorization": `Bearer ${getToken()}` } : {}),
       ...(init?.headers ?? {}),
     },
     ...init,
    });
  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("heimdall_token");
      window.location.href = "/login";
      return undefined as T;
     }
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
    conversation: (limit = 100) =>
      request<{ entries: ConversationEntry[] }>(`/api/pm/conversation?limit=${limit}`),
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

  schedules: {
    list: () => request<ScheduledTask[]>("/api/schedule"),
    create: (body: CreateScheduleBody) =>
      request<ScheduledTask>("/api/schedule", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Partial<ScheduledTask>) =>
      request<ScheduledTask>(`/api/schedule/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (id: string) => request(`/api/schedule/${id}`, { method: "DELETE" }),
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
    get: () => request<string>("/api/restrictions"),
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

  workspace: {
    files: (taskId: string) =>
      request<{ task_id: string; files: string[] }>(`/api/workspace/${taskId}/files`),
    file: (taskId: string, filename: string) =>
      request<WorkspaceFile>(`/api/workspace/${taskId}/file/${filename}`),
    diff: (taskId: string, fromFile: string, toFile: string) =>
      request<WorkspaceDiff>(`/api/workspace/${taskId}/diff?from_file=${fromFile}&to_file=${toFile}`),
  },

  webhooks: {
    list: () => request<{ webhooks: WebhookConfig[] }>("/api/webhooks"),
    add: (body: WebhookCreateBody) =>
      request<WebhookConfig>("/api/webhooks", { method: "POST", body: JSON.stringify(body) }),
    remove: (index: number) => request(`/api/webhooks/${index}`, { method: "DELETE" }),
    update: (index: number, body: Partial<WebhookConfig>) =>
      request<WebhookConfig>(`/api/webhooks/${index}`, { method: "PATCH", body: JSON.stringify(body) }),
    test: (index: number) => request<{ sent: boolean; url: string }>(`/api/webhooks/test/${index}`, { method: "POST" }),
     },

  config: {
    agents: () => request<AgentsConfig>("/api/config/agents"),
    updateAgent: (name: string, body: AgentConfigPatch) =>
      request<AgentConfig>(`/api/config/agents/${name}`, { method: "PATCH", body: JSON.stringify(body) }),
  },

  analytics: () => request<AnalyticsData>("/api/analytics"),

  models: {
    scan: () => request<ModelsResponse>("/api/models"),
    probe: (provider: string, url: string) =>
      request<{ available: boolean; models: string[]; error?: string }>(
        `/api/models/probe?provider=${encodeURIComponent(provider)}&url=${encodeURIComponent(url)}`
      ),
    validateKey: (provider: string, api_key: string) =>
      request<{ valid: boolean; models: string[]; error: string | null }>(
        "/api/models/validate-key",
        { method: "POST", body: JSON.stringify({ provider, api_key }) }
      ),
  },

  chat: {
    direct: (message: string, provider: string, model: string, session_id = "default") =>
      request<{ reply: string; provider: string; model: string; session_id: string }>(
        "/api/pm/chat/direct",
        { method: "POST", body: JSON.stringify({ message, provider, model, session_id }) }
      ),
  },

  project: {
    summary: () => request<ProjectSummary>("/api/project/summary"),
  },

  system: {
    info: () => request<SystemInfo>("/api/system/info"),
    updateStream: () => `${BASE}/api/system/update`,
  },

  github: {
    connect: (token: string) =>
      request<{ valid: boolean; error?: string; username?: string; name?: string; avatar_url?: string; public_repos?: number }>(
        "/api/github/connect", { method: "POST", body: JSON.stringify({ token }) }
      ),
    status: () => request<GHStatus>("/api/github/status"),
    disconnect: () => request("/api/github/disconnect", { method: "DELETE" }),
    repos: (page = 1, per_page = 30, sort = "updated") =>
      request<GHRepo[]>(`/api/github/repos?page=${page}&per_page=${per_page}&sort=${sort}`),
    clone: (repo_full_name: string, clone_url: string, set_active = true) =>
      request<{ action: string; local_path: string; repo: string; active: boolean }>(
        "/api/github/clone", { method: "POST", body: JSON.stringify({ repo_full_name, clone_url, set_active }) }
      ),
    setActive: (path: string) =>
      request<{ active_project_path: string }>("/api/github/set-active", { method: "POST", body: JSON.stringify({ path }) }),
    active: () => request<{ active_project_path: string | null }>("/api/github/active"),
  },

  setup: {
    status: () => request<{ configured: boolean; has_vault_key: boolean; has_api_token: boolean }>("/api/setup/status"),
    init: (body: { vault_key: string; api_token: string; anthropic_key?: string; ollama_url?: string }) =>
      request<{ ok: boolean; message: string }>("/api/setup/init", { method: "POST", body: JSON.stringify(body) }),
    generateKey: () => request<{ key: string }>("/api/setup/generate-key"),
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
    } catch { }
  };
  if (onError) es.onerror = onError;
  return () => es.close();
}

// ── Types ─────────────────────────────────────────────────────────────────────
export type TaskStatus =
  | "pending" | "in_progress" | "in_review" | "fixing"
  | "completed" | "failed" | "escalated";

export interface ReviewIssue {
  severity: string;
  description: string;
  location?: string;
}

export interface ReviewResult {
  approved: boolean;
  summary?: string;
  issues?: ReviewIssue[];
  feedback?: string;
  iteration?: number;
}

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
  latest_review?: ReviewResult;
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

export interface ScheduledTask {
  id: string;
  cron: string;
  task_template: {
    title: string;
    description: string;
    priority: string;
    tags: string[];
    depends_on: string[];
    max_review_iterations: number;
    output_path: string;
  };
  enabled: boolean;
  last_run?: string;
  next_run?: string;
}

export interface CreateScheduleBody {
  id?: string;
  cron: string;
  title: string;
  description: string;
  priority: string;
  tags: string[];
  depends_on: string[];
  max_review_iterations: number;
  output_path: string;
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

export interface WorkspaceFile {
  task_id: string;
  filename: string;
  content: string;
  size_bytes: number;
}

export interface WorkspaceDiff {
  task_id: string;
  from_file: string;
  to_file: string;
  diff: string;
}

export interface WebhookConfig {
  url: string;
  secret?: string;
  events: string[];
  enabled: boolean;
}

export interface WebhookCreateBody {
  url: string;
  secret?: string;
  events: string[];
  enabled: boolean;
}

export interface AgentConfig {
  model: string;
  provider: string;
  base_url?: string;
  temperature: number;
  max_tokens: number;
}

export interface AgentsConfig {
  worker: AgentConfig;
  reviewer: AgentConfig;
  orchestrator: AgentConfig;
}

export interface AgentConfigPatch {
  model?: string;
  provider?: string;
  base_url?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface ProviderInfo {
  available: boolean;
  models: string[];
  no_key?: boolean;
  base_url?: string;
  type: "local" | "cloud";
  label: string;
  description: string;
  key_name?: string;
  key_url?: string;
}

export interface ModelEntry {
  provider: string;
  model: string;
  label: string;
}

export interface ModelsResponse {
  providers: Record<string, ProviderInfo>;
  all_models: ModelEntry[];
}

export interface ConversationEntry {
  agent: "pm" | "worker" | "reviewer";
  label: string;
  content: string;
  task_id: string;
  iteration: number;
  type: "prompt" | "response";
  timestamp: number;
}

export interface SystemInfo {
  sha: string;
  branch: string;
  message: string;
  author: string;
  date: string;
  commits_behind: number;
  commits_ahead: number;
  install_dir?: string;
}

export interface GHStatus {
  connected: boolean;
  username?: string;
  name?: string;
  avatar_url?: string;
  active_project?: string | null;
  error?: string;
}

export interface GHRepo {
  full_name: string;
  name: string;
  description: string;
  private: boolean;
  language: string | null;
  stars: number;
  updated_at: string;
  clone_url: string;
  ssh_url: string;
  default_branch: string;
}

export interface ProjectSummary {
  git: {
    repo: string;
    branch: string;
    clean: boolean;
    staged: string[];
    unstaged: string[];
    recent_commits: GitCommit[];
  };
  tasks: {
    counts: { active: number; pending: number; completed: number; failed: number; escalated: number };
    active: { id: string; title: string; priority: string; status: string; tags: string[] }[];
    next_up: { id: string; title: string; priority: string; status: string; tags: string[] }[];
  };
}

export interface AnalyticsData {
  total_tasks: number;
  completed: number;
  failed: number;
  escalated: number;
  pending: number;
  success_rate: number;
  avg_iterations: number;
  avg_duration_seconds: number;
  tasks_by_priority: { low: number; medium: number; high: number; critical: number };
  tasks_by_tag: Record<string, number>;
  recent_completions: { id: string; title: string; completed_at: string; iterations: number }[];
}
