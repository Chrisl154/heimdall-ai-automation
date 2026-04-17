"use client";
import { useEffect, useState } from "react";
import { api, PMStatus, subscribeToEvents } from "@/lib/api";
import { Play, Square, Zap } from "lucide-react";

export function PMStatusBar() {
  const [status, setStatus] = useState<PMStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = () => api.pm.status().then(setStatus).catch(() => {});

  useEffect(() => {
    refresh();
    const unsub = subscribeToEvents(() => refresh());
    const interval = setInterval(refresh, 5000);
    return () => { unsub(); clearInterval(interval); };
  }, []);

  const toggle = async () => {
    if (!status) return;
    setLoading(true);
    try {
      if (status.running) await api.pm.stop();
      else await api.pm.start();
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  if (!status) return null;

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-card border-b border-border text-sm">
      <button
        onClick={toggle}
        disabled={loading}
        className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition-colors
          ${status.running ? "bg-destructive/20 text-destructive hover:bg-destructive/30" : "bg-primary/20 text-primary hover:bg-primary/30"}`}
      >
        {status.running ? <><Square className="w-3 h-3" /> Stop PM</> : <><Play className="w-3 h-3" /> Start PM</>}
      </button>

      <div className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full ${status.running ? "bg-green-400 pulse-dot" : "bg-muted-foreground"}`} />
        <span className="text-muted-foreground">{status.running ? "Running" : "Stopped"}</span>
      </div>

      {status.current_task_id && (
        <div className="flex items-center gap-1 text-primary">
          <Zap className="w-3 h-3" />
          <span>Processing: {status.current_task_id}</span>
        </div>
      )}

      <div className="ml-auto flex gap-4 text-muted-foreground">
        <span><span className="text-foreground font-medium">{status.tasks_pending}</span> pending</span>
        <span><span className="text-green-400 font-medium">{status.tasks_completed}</span> done</span>
        {status.tasks_escalated > 0 && (
          <span><span className="text-yellow-400 font-medium">{status.tasks_escalated}</span> escalated</span>
        )}
        {status.tasks_failed > 0 && (
          <span><span className="text-destructive font-medium">{status.tasks_failed}</span> failed</span>
        )}
      </div>
    </div>
  );
}
