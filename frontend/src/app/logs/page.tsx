"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { api, subscribeToEvents, PipelineEvent } from "@/lib/api";
import { Pause, Play, Trash2, RefreshCw, Download } from "lucide-react";

interface LogEntry extends PipelineEvent {
  localTime: string;
  source: "history" | "live";
}

type Tab = "events" | "app";
type EventCategory = "completed" | "escalated" | "failed" | "started" | "review" | "llm" | "approval" | "other";

const EVENT_CATEGORY: Record<string, EventCategory> = {
  task_completed:           "completed",
  review_approved:          "completed",
  commit_approved:          "completed",
  pm_started:               "completed",
  task_escalated:           "escalated",
  review_rejected:          "escalated",
  commit_declined:          "escalated",
  task_failed:              "failed",
  error:                    "failed",
  llm_call_failed:          "failed",
  task_started:             "started",
  task_sent_to_worker:      "started",
  pm_stopped:               "started",
  review_started:           "review",
  worker_output_received:   "review",
  fix_requested:            "review",
  llm_call_started:         "llm",
  llm_call_completed:       "llm",
  conversation_entry:       "llm",
  commit_approval_requested:"approval",
};

const CATEGORY_STYLE: Record<EventCategory, { badge: string; row: string }> = {
  completed: { badge: "bg-green-500/20 text-green-400",    row: "" },
  escalated: { badge: "bg-yellow-500/20 text-yellow-400",  row: "" },
  failed:    { badge: "bg-red-500/20 text-red-400",        row: "bg-red-500/5" },
  started:   { badge: "bg-blue-500/20 text-blue-400",      row: "" },
  review:    { badge: "bg-purple-500/20 text-purple-400",  row: "" },
  llm:       { badge: "bg-cyan-500/20 text-cyan-400",      row: "" },
  approval:  { badge: "bg-yellow-400/20 text-yellow-300",  row: "bg-yellow-400/5" },
  other:     { badge: "bg-secondary text-muted-foreground",row: "" },
};

const ALL_TYPES = [
  "pm_started", "pm_stopped",
  "task_started", "task_sent_to_worker", "worker_output_received",
  "review_started", "review_approved", "review_rejected", "fix_requested",
  "task_completed", "task_escalated", "task_failed", "error",
  "llm_call_started", "llm_call_completed", "llm_call_failed",
  "commit_approval_requested", "commit_approved", "commit_declined",
];

function fmtTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function nowStr(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function LogsPage() {
  const [tab, setTab] = useState<Tab>("events");
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState<Set<string>>(new Set());
  const [appLines, setAppLines] = useState<string[]>([]);
  const [appLoading, setAppLoading] = useState(false);
  const [appTotal, setAppTotal] = useState(0);

  const bottomRef = useRef<HTMLDivElement>(null);
  const appBottomRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(false);
  pausedRef.current = paused;

  // Load event history on mount
  const loadHistory = useCallback(async () => {
    try {
      const res = await api.logs.events(1000);
      setHistoryTotal(res.total);
      const loaded: LogEntry[] = res.events.map(ev => ({
        ...ev,
        localTime: fmtTime(ev.timestamp),
        source: "history" as const,
      }));
      setEntries(loaded);
      setHistoryLoaded(true);
    } catch {
      setHistoryLoaded(true);
    }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // Load app log
  const loadAppLog = useCallback(async () => {
    setAppLoading(true);
    try {
      const res = await api.logs.app(500);
      setAppLines(res.lines);
      setAppTotal(res.total);
    } catch { /* ignore */ }
    setAppLoading(false);
  }, []);

  useEffect(() => {
    if (tab === "app") loadAppLog();
  }, [tab, loadAppLog]);

  // Live SSE subscription
  useEffect(() => {
    const unsub = subscribeToEvents((ev: PipelineEvent) => {
      if (pausedRef.current) return;
      setEntries(prev => {
        const next = [...prev, { ...ev, localTime: nowStr(), source: "live" as const }];
        return next.length > 2000 ? next.slice(next.length - 2000) : next;
      });
    });
    return unsub;
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (!paused && tab === "events") bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, paused, tab]);

  useEffect(() => {
    if (tab === "app") appBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [appLines, tab]);

  const visible = filter.size === 0
    ? entries
    : entries.filter(e => filter.has(e.type));

  const toggleFilter = (type: string) =>
    setFilter(prev => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });

  const downloadEvents = () => {
    const blob = new Blob(
      [entries.map(e => `${e.localTime}  [${e.type}]${e.task_id ? ` [${e.task_id}]` : ""}  ${e.message}`).join("\n")],
      { type: "text/plain" }
    );
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `heimdall-events-${Date.now()}.txt`;
    a.click();
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-card shrink-0 flex-wrap">
        {/* Tabs */}
        <div className="flex gap-1 bg-secondary rounded-lg p-0.5 shrink-0">
          {(["events", "app"] as Tab[]).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3 py-1 rounded-md text-xs transition-colors ${tab === t ? "bg-card text-foreground shadow" : "text-muted-foreground hover:text-foreground"}`}>
              {t === "events" ? "Pipeline Events" : "App Log"}
            </button>
          ))}
        </div>

        {tab === "events" && (
          <>
            <div className="flex flex-wrap gap-1 flex-1 min-w-0">
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
                  clear
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-muted-foreground tabular-nums">
                {visible.length} shown{historyLoaded && historyTotal > 0 ? ` · ${historyTotal} total` : ""}
              </span>
              <button onClick={downloadEvents}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors" title="Download log">
                <Download className="w-3 h-3" />
              </button>
              <button onClick={() => setEntries([])}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive transition-colors">
                <Trash2 className="w-3 h-3" /> Clear
              </button>
              <button onClick={loadHistory}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors">
                <RefreshCw className="w-3 h-3" /> Reload
              </button>
              <button onClick={() => setPaused(p => !p)}
                className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${paused ? "bg-primary/20 text-primary" : "text-muted-foreground hover:text-foreground"}`}>
                {paused ? <><Play className="w-3 h-3" /> Resume</> : <><Pause className="w-3 h-3" /> Pause</>}
              </button>
            </div>
          </>
        )}

        {tab === "app" && (
          <div className="flex items-center gap-2 ml-auto shrink-0">
            {appTotal > 0 && (
              <span className="text-xs text-muted-foreground">{appTotal} total lines</span>
            )}
            <button onClick={loadAppLog} disabled={appLoading}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors">
              <RefreshCw className={`w-3 h-3 ${appLoading ? "animate-spin" : ""}`} /> Refresh
            </button>
          </div>
        )}
      </div>

      {/* ── Pipeline Events tab ─────────────────────────────────────────────── */}
      {tab === "events" && (
        <div className="flex-1 overflow-y-auto p-3 space-y-0.5 font-mono text-xs">
          {!historyLoaded && (
            <div className="flex items-center justify-center py-8 text-muted-foreground text-sm font-sans gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" /> Loading history…
            </div>
          )}
          {historyLoaded && visible.length === 0 && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm font-sans">
              No events yet. Start the PM to see activity.
            </div>
          )}
          {visible.map((e, i) => {
            const cat = EVENT_CATEGORY[e.type] ?? "other";
            const style = CATEGORY_STYLE[cat];
            return (
              <div key={i} className={`flex items-start gap-2 py-0.5 px-1 rounded ${style.row} ${e.source === "history" ? "opacity-70" : ""}`}>
                <span className="text-muted-foreground shrink-0 tabular-nums w-16">{e.localTime}</span>
                <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${style.badge}`}>
                  {e.type.replace(/_/g, " ")}
                </span>
                {e.task_id && (
                  <span className="text-primary shrink-0 font-mono">[{e.task_id}]</span>
                )}
                <span className="text-foreground/80 break-all leading-relaxed">{e.message}</span>
                {e.source === "history" && i === 0 && (
                  <span className="ml-auto text-[10px] text-muted-foreground/40 shrink-0">history</span>
                )}
              </div>
            );
          })}
          {historyLoaded && entries.length > 0 && (
            <div className="py-1 text-center text-[10px] text-muted-foreground/30 font-sans">
              ── live ──
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {/* ── App Log tab ─────────────────────────────────────────────────────── */}
      {tab === "app" && (
        <div className="flex-1 overflow-y-auto p-3 font-mono text-xs">
          {appLoading && (
            <div className="flex items-center justify-center py-8 text-muted-foreground text-sm font-sans gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" /> Loading…
            </div>
          )}
          {!appLoading && appLines.length === 0 && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm font-sans">
              logs/heimdall.log not found. Will appear after first run.
            </div>
          )}
          {appLines.map((line, i) => {
            const isError   = /ERROR|CRITICAL|Exception|Traceback/i.test(line);
            const isWarning = /WARNING|WARN/i.test(line);
            return (
              <div key={i} className={`py-0.5 break-all leading-relaxed ${isError ? "text-red-400" : isWarning ? "text-yellow-400" : "text-foreground/70"}`}>
                {line}
              </div>
            );
          })}
          <div ref={appBottomRef} />
        </div>
      )}
    </div>
  );
}
