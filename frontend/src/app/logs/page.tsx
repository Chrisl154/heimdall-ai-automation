"use client";
import { useEffect, useRef, useState } from "react";
import { subscribeToEvents, PipelineEvent } from "@/lib/api";
import { Pause, Play, Trash2 } from "lucide-react";

interface LogEntry extends PipelineEvent {
  localTime: string;
}

type EventCategory = "completed" | "escalated" | "failed" | "started" | "review" | "other";

const EVENT_CATEGORY: Record<string, EventCategory> = {
  task_completed:        "completed",
  review_approved:       "completed",
  pm_started:            "completed",
  task_escalated:        "escalated",
  review_rejected:       "escalated",
  task_failed:           "failed",
  error:                 "failed",
  task_started:          "started",
  task_sent_to_worker:   "started",
  pm_stopped:            "started",
  review_started:        "review",
  worker_output_received:"review",
  fix_requested:         "review",
};

const CATEGORY_STYLE: Record<EventCategory, { badge: string; dot: string }> = {
  completed: { badge: "bg-green-500/20 text-green-400",   dot: "bg-green-400" },
  escalated: { badge: "bg-yellow-500/20 text-yellow-400", dot: "bg-yellow-400" },
  failed:    { badge: "bg-red-500/20 text-red-400",       dot: "bg-red-400" },
  started:   { badge: "bg-blue-500/20 text-blue-400",     dot: "bg-blue-400" },
  review:    { badge: "bg-purple-500/20 text-purple-400", dot: "bg-purple-400" },
  other:     { badge: "bg-secondary text-muted-foreground", dot: "bg-muted-foreground" },
};

const ALL_TYPES = [
  "pm_started", "pm_stopped",
  "task_started", "task_sent_to_worker", "worker_output_received",
  "review_started", "review_approved", "review_rejected", "fix_requested",
  "task_completed", "task_escalated", "task_failed", "error",
];

function ts(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function LogsPage() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(false);

  pausedRef.current = paused;

  useEffect(() => {
    const unsub = subscribeToEvents((ev: PipelineEvent) => {
      setEntries(prev => {
        const next = [...prev, { ...ev, localTime: ts() }];
        return next.length > 500 ? next.slice(next.length - 500) : next;
      });
    });
    return unsub;
  }, []);

  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, paused]);

  const visible = filter.size === 0
    ? entries
    : entries.filter(e => filter.has(e.type));

  const toggleFilter = (type: string) =>
    setFilter(prev => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-card shrink-0 flex-wrap">
        <span className="text-sm font-medium shrink-0">Event Log</span>

        <div className="flex flex-wrap gap-1.5 flex-1">
          {ALL_TYPES.map(t => {
            const cat = EVENT_CATEGORY[t] ?? "other";
            const style = CATEGORY_STYLE[cat];
            const active = filter.has(t);
            return (
              <button key={t} onClick={() => toggleFilter(t)}
                className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${active ? style.badge + " border-transparent" : "border-border text-muted-foreground hover:border-primary/50"}`}>
                {t.replace(/_/g, " ")}
              </button>
            );
          })}
          {filter.size > 0 && (
            <button onClick={() => setFilter(new Set())} className="text-xs text-muted-foreground hover:text-foreground underline">
              clear filter
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => setEntries([])}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive transition-colors">
            <Trash2 className="w-3 h-3" /> Clear
          </button>
          <button onClick={() => setPaused(p => !p)}
            className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${paused ? "bg-primary/20 text-primary" : "text-muted-foreground hover:text-foreground"}`}>
            {paused ? <><Play className="w-3 h-3" /> Resume</> : <><Pause className="w-3 h-3" /> Pause</>}
          </button>
        </div>
      </div>

      {/* Log list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1 font-mono text-xs">
        {visible.length === 0 && (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm font-sans">
            Waiting for events…
          </div>
        )}
        {visible.map((e, i) => {
          const cat = EVENT_CATEGORY[e.type] ?? "other";
          const style = CATEGORY_STYLE[cat];
          return (
            <div key={i} className="flex items-start gap-2 py-0.5">
              <span className="text-muted-foreground shrink-0 tabular-nums">{e.localTime}</span>
              <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${style.badge}`}>
                {e.type.replace(/_/g, " ")}
              </span>
              {e.task_id && (
                <span className="text-primary shrink-0">[{e.task_id}]</span>
              )}
              <span className="text-foreground/80 break-all">{e.message}</span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
