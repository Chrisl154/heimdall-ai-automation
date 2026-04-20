"use client";
import { useEffect, useState } from "react";
import { api, Task, TaskStatus } from "@/lib/api";
import { Copy, CheckCircle2, AlertTriangle, X, FileText } from "lucide-react";

const STATUS_COLOR: Record<TaskStatus, string> = {
  pending:     "text-muted-foreground",
  in_progress: "text-blue-400",
  in_review:   "text-yellow-400",
  fixing:      "text-orange-400",
  completed:   "text-green-400",
  escalated:   "text-yellow-500",
  failed:      "text-red-400",
};

const PRIORITY_DOT: Record<string, string> = {
  critical: "bg-red-500", high: "bg-orange-400", medium: "bg-yellow-400", low: "bg-green-400",
};

interface WorkspaceFile { filename: string; content: string; size_bytes: number; }

export default function WorkspacePage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [wsFiles, setWsFiles] = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState<WorkspaceFile | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);
  const [copied, setCopied] = useState(false);
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");

  useEffect(() => {
    api.tasks.list().then(setTasks).catch(() => {});
  }, []);

  const selectTask = async (task: Task) => {
    setSelected(task);
    setActiveFile(null);
    setWsFiles([]);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/workspace/${task.id}/files`);
      if (res.ok) {
        const data = await res.json();
        setWsFiles(data.files ?? []);
      }
    } catch {}
  };

  const openFile = async (filename: string) => {
    if (!selected) return;
    setLoadingFile(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/workspace/${selected.id}/file/${filename}`);
      if (res.ok) setActiveFile(await res.json());
    } catch {}
    setLoadingFile(false);
  };

  const copy = async (text: string) => {
    await navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const grouped = ["all", "pending", "in_progress", "in_review", "fixing", "completed", "escalated", "failed"] as const;
  const visible = statusFilter === "all" ? tasks : tasks.filter(t => t.status === statusFilter);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: task list */}
      <div className="w-64 shrink-0 border-r border-border flex flex-col overflow-hidden">
        <div className="px-3 py-2 border-b border-border shrink-0">
          <select
            className="w-full bg-input border border-border rounded-lg px-2 py-1.5 text-xs outline-none focus:border-primary"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value as TaskStatus | "all")}>
            {grouped.map(s => <option key={s} value={s}>{s === "all" ? "All statuses" : s.replace(/_/g, " ")}</option>)}
          </select>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {visible.length === 0 && <p className="text-xs text-muted-foreground p-2">No tasks.</p>}
          {visible.map(task => (
            <button key={task.id} onClick={() => selectTask(task)}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs border transition-colors ${selected?.id === task.id ? "bg-primary/20 border-primary/40 text-foreground" : "bg-card border-border hover:border-primary/30 text-foreground"}`}>
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${PRIORITY_DOT[task.priority] ?? "bg-muted"}`} />
                <span className="font-mono text-muted-foreground">{task.id}</span>
              </div>
              <p className="font-medium leading-snug truncate">{task.title}</p>
              <p className={`text-[10px] mt-0.5 ${STATUS_COLOR[task.status]}`}>{task.status.replace(/_/g, " ")}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Right: task detail */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {!selected && (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Select a task to inspect its output.
          </div>
        )}

        {selected && (
          <>
            {/* Header */}
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="font-mono text-xs text-muted-foreground">{selected.id}</span>
                <span className={`text-xs font-medium ${STATUS_COLOR[selected.status]}`}>{selected.status.replace(/_/g, " ")}</span>
                <span className="text-xs bg-secondary px-2 py-0.5 rounded text-muted-foreground capitalize">{selected.priority}</span>
                {selected.tags.map(t => <span key={t} className="text-xs bg-secondary px-2 py-0.5 rounded text-muted-foreground">{t}</span>)}
              </div>
              <h2 className="text-base font-semibold">{selected.title}</h2>
            </div>

            {/* Timestamps */}
            <div className="flex gap-4 text-xs text-muted-foreground flex-wrap">
              {selected.created_at && <span>Created: <span className="text-foreground">{selected.created_at}</span></span>}
              {selected.started_at && <span>Started: <span className="text-foreground">{selected.started_at}</span></span>}
              {selected.completed_at && <span>Completed: <span className="text-foreground">{selected.completed_at}</span></span>}
            </div>

            {/* Iterations */}
            {selected.current_iteration > 0 && (
              <p className="text-xs text-muted-foreground">
                Review iterations: <span className="text-foreground font-medium">{selected.current_iteration}</span> / {selected.max_review_iterations}
              </p>
            )}

            {/* Error */}
            {selected.error && (
              <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3 flex gap-2 text-xs text-destructive">
                <X className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{selected.error}</span>
              </div>
            )}

            {/* Latest review */}
            {selected.latest_review && (
              <div className="bg-card border border-border rounded-xl p-4 space-y-2">
                <div className="flex items-center gap-2">
                  {selected.latest_review.approved
                    ? <><CheckCircle2 className="w-4 h-4 text-green-400" /><span className="text-sm font-medium text-green-400">Review Approved</span></>
                    : <><AlertTriangle className="w-4 h-4 text-yellow-400" /><span className="text-sm font-medium text-yellow-400">Review Rejected</span></>
                  }
                </div>
                {selected.latest_review.summary && <p className="text-xs text-muted-foreground">{selected.latest_review.summary}</p>}
                {(selected.latest_review.issues?.length ?? 0) > 0 && (
                  <ul className="space-y-1">
                    {selected.latest_review.issues!.map((issue: { severity: string; description: string; location?: string }, i: number) => (
                      <li key={i} className="text-xs flex gap-2">
                        <span className={`shrink-0 font-medium ${issue.severity === "critical" ? "text-red-400" : issue.severity === "major" ? "text-orange-400" : "text-yellow-400"}`}>
                          [{issue.severity}]
                        </span>
                        <span className="text-foreground/80">{issue.description}</span>
                        {issue.location && <span className="text-muted-foreground font-mono shrink-0">— {issue.location}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* Workspace files */}
            {wsFiles.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">Workspace Files</p>
                <div className="flex flex-wrap gap-2">
                  {wsFiles.map(f => (
                    <button key={f} onClick={() => openFile(f)}
                      className={`flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg border transition-colors ${activeFile?.filename === f ? "bg-primary/20 border-primary/40 text-primary" : "bg-card border-border text-muted-foreground hover:border-primary/30 hover:text-foreground"}`}>
                      <FileText className="w-3 h-3" />{f}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* File content */}
            {activeFile && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-muted-foreground font-mono">{activeFile.filename}
                    <span className="ml-2 text-muted-foreground/60">({(activeFile.size_bytes / 1024).toFixed(1)} KB)</span>
                  </p>
                  <button onClick={() => copy(activeFile.content)}
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors">
                    <Copy className="w-3 h-3" />
                    {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
                <pre className="bg-secondary/50 rounded-xl p-4 text-xs overflow-x-auto overflow-y-auto max-h-[500px] whitespace-pre-wrap break-all">
                  {activeFile.content}
                </pre>
              </div>
            )}

            {loadingFile && <p className="text-xs text-muted-foreground">Loading…</p>}

            {/* Output path */}
            {selected.output_path && (
              <p className="text-xs text-muted-foreground font-mono border-t border-border pt-3">
                Output path: {selected.output_path}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
