"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { api, ProjectSummary, PipelineEvent, subscribeToEvents } from "@/lib/api";
import {
  GitBranch, CheckCircle2, Circle, AlertTriangle, Clock,
  RefreshCw, GitCommit, Bot, Zap, FileEdit, MessagesSquare,
} from "lucide-react";

const STATUS_COLOR: Record<string, string> = {
  in_progress: "text-blue-400",
  in_review:   "text-violet-400",
  fixing:      "text-yellow-400",
  pending:     "text-muted-foreground",
  completed:   "text-green-400",
  failed:      "text-red-400",
  escalated:   "text-orange-400",
};

const PRIORITY_DOT: Record<string, string> = {
  critical: "bg-red-400",
  high:     "bg-orange-400",
  medium:   "bg-yellow-400",
  low:      "bg-green-400",
};

const AGENT_LABELS: Record<string, string> = {
  task_sent_to_worker:     "Worker (Qwen)",
  worker_output_received:  "Worker (Qwen)",
  review_started:          "Reviewer (Claude)",
  review_approved:         "Reviewer (Claude)",
  review_rejected:         "Reviewer (Claude)",
  fix_requested:           "Reviewer (Claude)",
  task_completed:          "PM (Gemma)",
  task_escalated:          "PM (Gemma)",
  task_failed:             "PM (Gemma)",
  pm_started:              "PM (Gemma)",
  pm_stopped:              "PM (Gemma)",
  task_started:            "PM (Gemma)",
  pm_chat_response:        "PM (Gemma)",
};

const AGENT_COLOR: Record<string, string> = {
  "Worker (Qwen)":    "text-emerald-400 bg-emerald-400/10",
  "Reviewer (Claude)":"text-orange-400 bg-orange-400/10",
  "PM (Gemma)":       "text-violet-400 bg-violet-400/10",
};

interface AgentMessage { agent: string; content: string; time: string; type: string; }

function timeStr() { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }

export default function ProjectPage() {
  const [summary, setSummary]     = useState<ProjectSummary | null>(null);
  const [loading, setLoading]     = useState(true);
  const [events, setEvents]       = useState<PipelineEvent[]>([]);
  const [agentLog, setAgentLog]   = useState<AgentMessage[]>([]);
  const eventsRef = useRef<HTMLDivElement>(null);
  const agentRef  = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const s = await api.project.summary();
      setSummary(s);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const REFRESH_EVENTS = new Set([
    "task_started", "task_completed", "task_failed", "task_escalated",
    "review_approved", "pm_started", "pm_stopped",
  ]);

  useEffect(() => {
    const unsub = subscribeToEvents((ev: PipelineEvent) => {
      setEvents(prev => [ev, ...prev].slice(0, 100));
      const agent = AGENT_LABELS[ev.type] ?? "PM (Gemma)";
      if (ev.message) {
        setAgentLog(prev => [
          { agent, content: ev.message, time: timeStr(), type: ev.type },
          ...prev,
        ].slice(0, 200));
      }
      if (REFRESH_EVENTS.has(ev.type)) {
        load();
      }
    });
    return unsub;
  }, [load]);

  useEffect(() => {
    eventsRef.current?.scrollTo({ top: 0 });
  }, [events]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex items-center gap-3 text-muted-foreground">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading project…</span>
        </div>
      </div>
    );
  }

  const git = summary?.git;
  const tasks = summary?.tasks;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto w-full">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">{git?.repo ?? "Project"}</h1>
            <span className="flex items-center gap-1 text-xs px-2 py-0.5 bg-secondary border border-border rounded-full text-muted-foreground font-mono">
              <GitBranch className="w-3 h-3" />
              {git?.branch ?? "unknown"}
            </span>
            {git && (
              <span className={`text-xs px-2 py-0.5 rounded-full border ${git.clean ? "text-green-400 bg-green-400/10 border-green-400/20" : "text-yellow-400 bg-yellow-400/10 border-yellow-400/20"}`}>
                {git.clean ? "clean" : `${git.unstaged.length + git.staged.length} change${git.unstaged.length + git.staged.length !== 1 ? "s" : ""}`}
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">Live project dashboard</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-3 py-1.5 text-sm bg-secondary border border-border rounded-lg hover:bg-secondary/70 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Task counts */}
      {tasks && (
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: "Active",    count: tasks.counts.active,    color: "text-blue-400",   bg: "bg-blue-400/10" },
            { label: "Pending",   count: tasks.counts.pending,   color: "text-muted-foreground", bg: "bg-secondary" },
            { label: "Done",      count: tasks.counts.completed, color: "text-green-400",  bg: "bg-green-400/10" },
            { label: "Failed",    count: tasks.counts.failed,    color: "text-red-400",    bg: "bg-red-400/10" },
            { label: "Escalated", count: tasks.counts.escalated, color: "text-orange-400", bg: "bg-orange-400/10" },
          ].map(({ label, count, color, bg }) => (
            <div key={label} className={`${bg} border border-border rounded-xl p-3 text-center`}>
              <div className={`text-2xl font-bold ${color}`}>{count}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">

        {/* Active work */}
        <section className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-semibold">Active Work</h2>
          </div>
          <div className="divide-y divide-border">
            {tasks?.active.length === 0 && (
              <p className="px-4 py-6 text-xs text-muted-foreground text-center">No active tasks</p>
            )}
            {tasks?.active.map(t => (
              <div key={t.id} className="px-4 py-3 flex items-start gap-3">
                <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${PRIORITY_DOT[t.priority] ?? "bg-gray-400"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm truncate">{t.title}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-xs font-mono ${STATUS_COLOR[t.status] ?? "text-muted-foreground"}`}>{t.status.replace("_", " ")}</span>
                    {t.tags.slice(0, 2).map(tag => (
                      <span key={tag} className="text-xs px-1.5 py-0.5 bg-secondary rounded text-muted-foreground">{tag}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Next up */}
        <section className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <Clock className="w-4 h-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Next Up</h2>
          </div>
          <div className="divide-y divide-border">
            {tasks?.next_up.length === 0 && (
              <p className="px-4 py-6 text-xs text-muted-foreground text-center">Queue is empty</p>
            )}
            {tasks?.next_up.map(t => (
              <div key={t.id} className="px-4 py-3 flex items-start gap-3">
                <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${PRIORITY_DOT[t.priority] ?? "bg-gray-400"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm truncate">{t.title}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-muted-foreground">{t.priority}</span>
                    {t.tags.slice(0, 2).map(tag => (
                      <span key={tag} className="text-xs px-1.5 py-0.5 bg-secondary rounded text-muted-foreground">{tag}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Git section */}
      {git && (
        <section className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Git</h2>
            <span className="text-xs text-muted-foreground font-mono ml-auto">{git.branch}</span>
          </div>
          <div className="grid grid-cols-2 gap-0 divide-x divide-border">
            {/* Changed files */}
            <div className="p-4">
              <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider mb-2">Changed Files</p>
              {git.staged.length === 0 && git.unstaged.length === 0 ? (
                <div className="flex items-center gap-2 text-xs text-green-400">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Working tree clean
                </div>
              ) : (
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {git.staged.map(f => (
                    <div key={f} className="flex items-center gap-2 text-xs font-mono">
                      <FileEdit className="w-3 h-3 text-green-400 shrink-0" />
                      <span className="truncate text-foreground/80">{f}</span>
                      <span className="text-green-400 text-[10px] ml-auto">staged</span>
                    </div>
                  ))}
                  {git.unstaged.map(f => (
                    <div key={f} className="flex items-center gap-2 text-xs font-mono">
                      <FileEdit className="w-3 h-3 text-yellow-400 shrink-0" />
                      <span className="truncate text-foreground/80">{f}</span>
                      <span className="text-yellow-400 text-[10px] ml-auto">modified</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {/* Recent commits */}
            <div className="p-4">
              <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider mb-2">Recent Commits</p>
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {git.recent_commits.length === 0 && (
                  <p className="text-xs text-muted-foreground">No commits found</p>
                )}
                {git.recent_commits.slice(0, 5).map(c => (
                  <div key={c.sha} className="flex items-start gap-2">
                    <GitCommit className="w-3 h-3 text-muted-foreground shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <p className="text-xs truncate">{c.message}</p>
                      <p className="text-[10px] text-muted-foreground font-mono">{c.sha.slice(0, 7)} · {c.author}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      <div className="grid grid-cols-2 gap-4">

        {/* Live activity feed */}
        <section className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-semibold">Activity Feed</h2>
            <span className="ml-auto text-[10px] text-muted-foreground">live</span>
          </div>
          <div ref={eventsRef} className="divide-y divide-border max-h-72 overflow-y-auto">
            {events.length === 0 && (
              <p className="px-4 py-6 text-xs text-muted-foreground text-center">Waiting for events…</p>
            )}
            {events.map((ev, i) => (
              <div key={i} className="px-4 py-2.5 flex items-start gap-2">
                <Circle className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0 text-transparent" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-foreground/80 truncate">{ev.message || ev.type}</p>
                  <p className="text-[10px] text-muted-foreground font-mono">
                    {ev.task_id ? `${ev.task_id.slice(0, 8)} · ` : ""}{ev.type}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Agent conversation thread */}
        <section className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <MessagesSquare className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-semibold">Agent Conversation</h2>
          </div>
          <div ref={agentRef} className="divide-y divide-border max-h-72 overflow-y-auto">
            {agentLog.length === 0 && (
              <p className="px-4 py-6 text-xs text-muted-foreground text-center">No agent activity yet…</p>
            )}
            {agentLog.map((msg, i) => {
              const colorClass = AGENT_COLOR[msg.agent] ?? "text-muted-foreground bg-secondary";
              return (
                <div key={i} className="px-4 py-3 flex items-start gap-3">
                  <Bot className="w-4 h-4 shrink-0 mt-0.5 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${colorClass}`}>{msg.agent}</span>
                      <span className="text-[10px] text-muted-foreground font-mono">{msg.time}</span>
                    </div>
                    <p className="text-xs text-foreground/80 whitespace-pre-wrap line-clamp-4">{msg.content}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* Untracked / extra changed files */}
      {git && !git.clean && (
        <section className="bg-yellow-400/5 border border-yellow-400/20 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            <h2 className="text-sm font-semibold text-yellow-400">Uncommitted Changes</h2>
          </div>
          <div className="grid grid-cols-2 gap-1">
            {[...git.staged, ...git.unstaged].map(f => (
              <div key={f} className="flex items-center gap-2 text-xs font-mono text-foreground/70">
                <FileEdit className="w-3 h-3 text-yellow-400 shrink-0" /> {f}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
