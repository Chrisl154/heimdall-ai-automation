"use client";
import { useEffect, useState, useCallback } from "react";
import { api, Task, TaskStatus, subscribeToEvents, CreateTaskBody } from "@/lib/api";
import { PMStatusBar } from "@/components/PMStatusBar";
import { Plus, X, AlertTriangle, CheckCircle2, Loader2, Clock, Eye, RefreshCw } from "lucide-react";

const COLUMNS: { id: TaskStatus; label: string; color: string }[] = [
  { id: "pending",     label: "Pending",     color: "text-muted-foreground" },
  { id: "in_progress", label: "In Progress", color: "text-blue-400" },
  { id: "in_review",   label: "In Review",   color: "text-yellow-400" },
  { id: "fixing",      label: "Fixing",      color: "text-orange-400" },
  { id: "completed",   label: "Done",        color: "text-green-400" },
  { id: "escalated",   label: "Escalated",   color: "text-yellow-500" },
  { id: "failed",      label: "Failed",      color: "text-red-400" },
];

const STATUS_ICON: Record<TaskStatus, React.ReactNode> = {
  pending:     <Clock className="w-3 h-3" />,
  in_progress: <Loader2 className="w-3 h-3 animate-spin" />,
  in_review:   <Eye className="w-3 h-3" />,
  fixing:      <RefreshCw className="w-3 h-3 animate-spin" />,
  completed:   <CheckCircle2 className="w-3 h-3" />,
  escalated:   <AlertTriangle className="w-3 h-3" />,
  failed:      <X className="w-3 h-3" />,
};

const PRIORITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  high:     "bg-orange-400",
  medium:   "bg-yellow-400",
  low:      "bg-green-400",
};

interface NewTaskForm { title: string; description: string; priority: Task["priority"]; }

export default function KanbanPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<NewTaskForm>({ title: "", description: "", priority: "medium" });
  const [saving, setSaving] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [templateList, setTemplateList] = useState<Array<{ id: string; label: string; priority: string; tags: string[]; description_template: string }>>([]);

  const refresh = useCallback(() => { api.tasks.list().then(setTasks).catch(() => {}); }, []);

  useEffect(() => {
    refresh();
    const unsub = subscribeToEvents(() => refresh());
    return unsub;
  }, [refresh]);

  useEffect(() => {
    if (showAdd) {
      fetch("/api/templates").then(r => r.json()).then(setTemplateList).catch(() => {});
    }
  }, [showAdd]);

  const byStatus = (s: TaskStatus) => tasks.filter(t => t.status === s);

  const addTask = async () => {
    if (!form.title.trim()) return;
    setSaving(true);
    const body: CreateTaskBody = { title: form.title, description: form.description, priority: form.priority };
    await api.tasks.create(body).catch(() => {});
    await refresh();
    setForm({ title: "", description: "", priority: "medium" });
    setShowAdd(false);
    setSelectedTemplateId(null);
    setSaving(false);
  };

  return (
    <div className="flex flex-col h-full">
      <PMStatusBar />
      <div className="flex items-center justify-between px-6 py-3 border-b border-border">
        <h1 className="text-lg font-semibold">Task Board</h1>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 text-sm bg-primary/20 text-primary hover:bg-primary/30 px-3 py-1.5 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" /> New Task
        </button>
      </div>

      <div className="flex-1 overflow-x-auto overflow-y-hidden">
        <div className="flex h-full gap-3 p-4 min-w-max">
          {COLUMNS.map(col => (
            <div key={col.id} className="w-64 flex flex-col bg-card rounded-xl border border-border overflow-hidden shrink-0">
              <div className="px-3 py-2.5 border-b border-border flex items-center justify-between">
                <span className={`text-xs font-semibold uppercase tracking-wide ${col.color}`}>{col.label}</span>
                <span className="text-xs bg-secondary text-muted-foreground rounded-full px-1.5 py-0.5">{byStatus(col.id).length}</span>
              </div>
              <div className="flex-1 overflow-y-auto p-2 space-y-2">
                {byStatus(col.id).map(task => (
                  <button
                    key={task.id}
                    onClick={() => setSelected(task)}
                    className="w-full text-left bg-background rounded-lg p-3 border border-border hover:border-primary/50 transition-colors"
                  >
                    <div className="flex items-start gap-2">
                      <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${PRIORITY_DOT[task.priority] ?? "bg-muted"}`} />
                      <span className="text-sm font-medium leading-snug">{task.title}</span>
                    </div>
                    <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span className={col.color}>{STATUS_ICON[task.status]}</span>
                      {task.current_iteration > 0 && <span>iter {task.current_iteration}</span>}
                      <div className="ml-auto flex gap-1 flex-wrap">
                        {task.tags.slice(0, 2).map(tag => (
                          <span key={tag} className="bg-secondary px-1.5 py-0.5 rounded text-xs">{tag}</span>
                        ))}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Task detail panel */}
      {selected && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-6" onClick={() => setSelected(null)}>
          <div className="bg-card border border-border rounded-2xl w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <span className="text-xs text-muted-foreground font-mono">{selected.id}</span>
                <h2 className="text-lg font-semibold mt-0.5">{selected.title}</h2>
              </div>
              <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex gap-2 flex-wrap">
                <span className={`px-2 py-1 rounded text-xs font-medium bg-secondary ${COLUMNS.find(c => c.id === selected.status)?.color}`}>
                  {selected.status.replace("_", " ")}
                </span>
                <span className="px-2 py-1 rounded text-xs bg-secondary text-muted-foreground capitalize">{selected.priority}</span>
                {selected.tags.map(t => <span key={t} className="px-2 py-1 rounded text-xs bg-secondary text-muted-foreground">{t}</span>)}
              </div>
              <div className="bg-secondary/50 rounded-lg p-3 text-muted-foreground whitespace-pre-wrap text-xs leading-relaxed">{selected.description}</div>
              {selected.current_iteration > 0 && (
                <p className="text-muted-foreground">Review iterations: <span className="text-foreground">{selected.current_iteration} / {selected.max_review_iterations}</span></p>
              )}
              {selected.error && (
                <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3 text-xs text-destructive">{selected.error}</div>
              )}
              {selected.latest_output && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Latest Output Preview</p>
                  <pre className="bg-secondary/50 rounded-lg p-3 text-xs overflow-x-auto whitespace-pre-wrap max-h-48">{selected.latest_output.slice(0, 2000)}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add task modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-6" onClick={() => setShowAdd(false)}>
          <div className="bg-card border border-border rounded-2xl w-full max-w-lg p-6" onClick={e => e.stopPropagation()}>
            <h2 className="font-semibold mb-4">New Task</h2>
            <div className="space-y-3">
              {templateList.length > 0 && (
                <select
                  className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                  value={selectedTemplateId ?? ""}
                  onChange={e => {
                    const id = e.target.value;
                    const tmpl = templateList.find(t => t.id === id);
                    if (tmpl) {
                      setForm(f => ({
                        ...f,
                        description: tmpl.description_template.replace("{{user_spec}}", ""),
                        priority: tmpl.priority as Task["priority"],
                      }));
                      setSelectedTemplateId(id);
                    } else {
                      setSelectedTemplateId(null);
                    }
                  }}
                >
                  <option value="">Select a template (optional)</option>
                  {templateList.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
                </select>
              )}
              <input
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="Task title"
                value={form.title}
                onChange={e => setForm(p => ({ ...p, title: e.target.value }))}
              />
              <textarea
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary resize-none h-32"
                placeholder="Description (tell Qwen exactly what to build)"
                value={form.description}
                onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
              />
              <select
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                value={form.priority}
                onChange={e => setForm(p => ({ ...p, priority: e.target.value as Task["priority"] }))}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={() => setShowAdd(false)} className="flex-1 bg-secondary text-foreground py-2 rounded-lg text-sm hover:bg-secondary/80">Cancel</button>
              <button onClick={addTask} disabled={saving || !form.title.trim()} className="flex-1 bg-primary text-primary-foreground py-2 rounded-lg text-sm hover:opacity-90 disabled:opacity-50">
                {saving ? "Adding…" : "Add Task"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
