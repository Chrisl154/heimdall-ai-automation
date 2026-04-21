"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { api, ClaudeUsage, ConversationEntry, ModelsResponse, PipelineEvent, subscribeToEvents } from "@/lib/api";
import { PMStatusBar } from "@/components/PMStatusBar";
import { Send, Bot, User, Zap, ChevronDown, MessagesSquare, X, ChevronRight, RefreshCw } from "lucide-react";

interface Message { role: "user" | "assistant" | "event"; content: string; time: string; model?: string; }
interface SelectedModel { provider: string; model: string; label: string; }

function now() { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

function formatClaudeReset(resetStr?: string): string {
  if (!resetStr) return "";
  const diffMs = new Date(resetStr).getTime() - Date.now();
  if (diffMs <= 0) return "resetting…";
  const mins = Math.ceil(diffMs / 60000);
  return `~${mins}m`;
}

// ── Agent conversation panel ──────────────────────────────────────────────────

const AGENT_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  pm:       { bg: "bg-violet-400/10", border: "border-violet-400/20", text: "text-violet-400", dot: "bg-violet-400" },
  worker:   { bg: "bg-emerald-400/10", border: "border-emerald-400/20", text: "text-emerald-400", dot: "bg-emerald-400" },
  reviewer: { bg: "bg-orange-400/10", border: "border-orange-400/20", text: "text-orange-400", dot: "bg-orange-400" },
};

function AgentBubble({ entry, expanded, onToggle }: {
  entry: ConversationEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  const colors = AGENT_COLORS[entry.agent] ?? AGENT_COLORS.pm;
  const isPrompt = entry.type === "prompt";
  const preview = entry.content.slice(0, 200);
  const hasMore = entry.content.length > 200;

  return (
    <div className={`rounded-xl border ${colors.bg} ${colors.border} p-3 space-y-1.5`}>
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full shrink-0 ${colors.dot}`} />
        <span className={`text-xs font-semibold ${colors.text}`}>{entry.label}</span>
        {entry.iteration > 0 && (
          <span className="text-[10px] text-muted-foreground ml-auto">iter {entry.iteration}</span>
        )}
        <span className="text-[10px] text-muted-foreground font-mono">
          {new Date(entry.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
        </span>
        {entry.duration_ms != null && entry.duration_ms > 0 && (
          <span className="text-[10px] text-muted-foreground">· {(entry.duration_ms / 1000).toFixed(1)}s</span>
        )}
        {entry.tokens?.output_tokens != null && entry.tokens.output_tokens > 0 && (
          <span className="text-[10px] text-muted-foreground">· {entry.tokens.output_tokens.toLocaleString()} tok</span>
        )}
      </div>

      {/* Content */}
      <div
        className={`text-xs font-mono whitespace-pre-wrap break-words leading-relaxed
          ${isPrompt ? "text-muted-foreground" : "text-foreground/80"}`}
        style={{ maxHeight: expanded ? "none" : "5rem", overflow: expanded ? "visible" : "hidden" }}
      >
        {expanded ? entry.content : preview}
      </div>

      {hasMore && (
        <button
          onClick={onToggle}
          className={`flex items-center gap-1 text-[10px] ${colors.text} hover:opacity-80 transition-opacity`}
        >
          {expanded
            ? <><ChevronDown className="w-3 h-3" /> Collapse</>
            : <><ChevronRight className="w-3 h-3" /> Show {entry.content.length - 200} more chars</>
          }
        </button>
      )}
    </div>
  );
}

const PANEL_ONLY = new Set(["conversation_entry", "llm_call_started", "llm_call_completed", "llm_call_failed", "pm_chat_response", "commit_approval_requested"]);

interface ApprovalInfo { title: string; audit?: string; output_preview?: string; }

function ApprovalCard({ taskId, info, onApprove, onDecline }: {
  taskId: string;
  info: ApprovalInfo;
  onApprove: (id: string) => Promise<void>;
  onDecline: (id: string) => Promise<void>;
}) {
  const [working, setWorking] = useState(false);
  const [showAudit, setShowAudit] = useState(false);

  const approve = async () => {
    setWorking(true);
    await onApprove(taskId);
    setWorking(false);
  };
  const decline = async () => {
    setWorking(true);
    await onDecline(taskId);
    setWorking(false);
  };

  return (
    <div className="bg-yellow-400/10 border border-yellow-400/30 rounded-xl p-3 space-y-2">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2 h-2 rounded-full bg-yellow-400 shrink-0" />
          <span className="text-xs font-medium text-yellow-300 truncate">Ready to commit: {info.title}</span>
        </div>
        {info.audit && (
          <button
            onClick={() => setShowAudit(p => !p)}
            className="text-[10px] text-muted-foreground hover:text-foreground transition-colors shrink-0"
          >
            {showAudit ? "Hide audit ▲" : "View re-audit ▼"}
          </button>
        )}
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <button
            onClick={decline}
            disabled={working}
            className="text-xs px-3 py-1 border border-yellow-400/30 text-yellow-400 rounded-lg hover:bg-yellow-400/10 disabled:opacity-40 transition-colors"
          >
            {working ? "Working…" : "Decline & Re-audit"}
          </button>
          <button
            onClick={approve}
            disabled={working}
            className="text-xs px-3 py-1 bg-green-400/20 text-green-400 border border-green-400/30 rounded-lg hover:bg-green-400/30 disabled:opacity-40 transition-colors font-medium"
          >
            Approve & Commit
          </button>
        </div>
      </div>
      {showAudit && info.audit && (
        <pre className="text-[10px] text-muted-foreground font-mono bg-background/60 border border-border rounded-lg p-2 whitespace-pre-wrap max-h-48 overflow-y-auto">
          {info.audit}
        </pre>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hello! I'm Heimdall, your AI Project Manager. You can ask me about task status, start/stop the pipeline, or give me new tasks.", time: now() },
  ]);
  const [input, setInput]             = useState("");
  const [loading, setLoading]         = useState(false);
  const [modelsData, setModelsData]   = useState<ModelsResponse | null>(null);
  const [selected, setSelected]       = useState<SelectedModel | null>(null);
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [showPanel, setShowPanel]     = useState(true);
  const [conversation, setConversation] = useState<ConversationEntry[]>([]);
  const [convLoading, setConvLoading] = useState(false);
  const [expanded, setExpanded]       = useState<Record<number, boolean>>({});
  const [claudeUsage, setClaudeUsage] = useState<ClaudeUsage | null>(null);
  const [pendingCall, setPendingCall] = useState<{ provider: string; model: string; agent: string } | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<Record<string, ApprovalInfo>>({});
  const [sessionStats, setSessionStats] = useState<Record<string, { calls: number; input_tokens: number; output_tokens: number; total_ms: number }>>({});

  const bottomRef   = useRef<HTMLDivElement>(null);
  const convBottomRef = useRef<HTMLDivElement>(null);
  const selectorRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => { convBottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [conversation]);

  useEffect(() => { api.models.scan().then(setModelsData).catch(() => {}); }, []);

  useEffect(() => {
    api.pm.chatHistory().then(res => {
      if (res.messages.length > 0) {
        const loaded: Message[] = res.messages.map(m => ({
          role: m.role as "user" | "assistant",
          content: m.content,
          time: "",
        }));
        setMessages([
          { role: "assistant", content: "Hello! I'm Heimdall, your AI Project Manager. You can ask me about task status, start/stop the pipeline, or give me new tasks.", time: now() },
          ...loaded,
        ]);
      }
    }).catch(() => {});
  }, []);

  const loadConversation = useCallback(async () => {
    setConvLoading(true);
    try {
      const res = await api.pm.conversation(200);
      setConversation(res.entries);
    } catch { /* ignore */ }
    setConvLoading(false);
  }, []);

  useEffect(() => {
    if (showPanel) loadConversation();
  }, [showPanel, loadConversation]);

  const refreshClaudeUsage = useCallback(() => {
    api.pm.claudeUsage().then(setClaudeUsage).catch(() => {});
  }, []);

  useEffect(() => { refreshClaudeUsage(); }, [refreshClaudeUsage]);

  // Close model selector on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node))
        setSelectorOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // SSE events — chat feed + live conversation updates
  useEffect(() => {
    const unsub = subscribeToEvents((ev: PipelineEvent) => {
      // Main chat feed — skip panel-only events
      if (ev.message && !PANEL_ONLY.has(ev.type)) {
        setMessages(prev => [...prev, { role: "event", content: ev.message, time: now() }]);
      }
      // Live conversation panel — push entries directly
      if (ev.type === "conversation_entry" && ev.data?.entry) {
        setConversation(prev => [...prev, ev.data.entry as ConversationEntry]);
      }
      // Track pending LLM call for spinner
      if (ev.type === "llm_call_started") {
        setPendingCall(ev.data as { provider: string; model: string; agent: string });
      }
      if (ev.type === "llm_call_completed" || ev.type === "llm_call_failed") {
        setPendingCall(null);
        refreshClaudeUsage();
        // Accumulate per-provider session stats
        if (ev.type === "llm_call_completed") {
          const key = `${ev.data.provider}/${ev.data.model}`;
          setSessionStats(prev => ({
            ...prev,
            [key]: {
              calls: (prev[key]?.calls ?? 0) + 1,
              input_tokens: (prev[key]?.input_tokens ?? 0) + Number(ev.data.input_tokens ?? 0),
              output_tokens: (prev[key]?.output_tokens ?? 0) + Number(ev.data.output_tokens ?? 0),
              total_ms: (prev[key]?.total_ms ?? 0) + Number(ev.data.duration_ms ?? 0),
            },
          }));
        }
      }
      // Commit approval gate
      if (ev.type === "commit_approval_requested" && ev.task_id) {
        const d = ev.data as unknown as ApprovalInfo;
        setPendingApprovals(prev => ({ ...prev, [ev.task_id!]: d }));
      }
      if (ev.type === "commit_approved" && ev.task_id) {
        setPendingApprovals(prev => { const n = { ...prev }; delete n[ev.task_id!]; return n; });
      }
    });
    return unsub;
  }, [refreshClaudeUsage]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: text, time: now() }]);
    setLoading(true);
    try {
      let reply: string;
      if (selected) {
        const res = await api.chat.direct(text, selected.provider, selected.model);
        reply = res.reply;
      } else {
        const res = await api.pm.chat(text);
        reply = res.reply;
      }
      setMessages(prev => [...prev, {
        role: "assistant", content: reply, time: now(),
        model: selected ? selected.label : "PM (Gemma)",
      }]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${msg}`, time: now() }]);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (taskId: string) => {
    await api.pm.approveCommit(taskId).catch(() => {});
  };

  const handleDecline = async (taskId: string) => {
    await api.pm.declineCommit(taskId).catch(() => {});
    // pendingApprovals will update via SSE commit_approval_requested with audit
  };

  const pmOption: SelectedModel = { provider: "pm", model: "orchestrator", label: "PM (Gemma)" };
  const allOptions: SelectedModel[] = [
    pmOption,
    ...(modelsData?.all_models.map(m => ({ provider: m.provider, model: m.model, label: m.label })) ?? []),
  ];
  const activeLabel = selected?.label ?? pmOption.label;

  return (
    <div className="flex flex-col h-full">
      <PMStatusBar />

      {/* Model selector + panel toggle bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-card/50">
        <span className="text-xs text-muted-foreground">Chat with:</span>
        <div className="relative" ref={selectorRef}>
          <button
            onClick={() => setSelectorOpen(o => !o)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-secondary border border-border rounded-lg hover:bg-secondary/70 transition-colors"
          >
            <Bot className="w-3.5 h-3.5 text-primary" />
            {activeLabel}
            <ChevronDown className="w-3 h-3 text-muted-foreground" />
          </button>
          {selectorOpen && (
            <div className="absolute top-full left-0 mt-1 w-72 bg-popover border border-border rounded-xl shadow-xl z-50 py-1 max-h-72 overflow-y-auto">
              {allOptions.map(opt => {
                const isActive = opt.provider === (selected?.provider ?? "pm") && opt.model === (selected?.model ?? "orchestrator");
                return (
                  <button
                    key={`${opt.provider}/${opt.model}`}
                    onClick={() => { setSelected(opt.provider === "pm" ? null : opt); setSelectorOpen(false); }}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-secondary transition-colors ${isActive ? "text-primary" : "text-foreground"}`}
                  >
                    <Bot className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-primary" : "text-muted-foreground"}`} />
                    <span className="truncate">{opt.label}</span>
                    {isActive && <span className="ml-auto text-primary text-[10px]">active</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2">
          {claudeUsage?.["tokens-remaining"] && (
            <div className="flex items-center gap-1 px-2 py-1 text-[10px] bg-orange-400/10 border border-orange-400/20 rounded text-orange-300 font-mono">
              <span>Claude {Number(claudeUsage["tokens-remaining"]).toLocaleString()}/{Number(claudeUsage["tokens-limit"]).toLocaleString()} tok</span>
              {claudeUsage["tokens-reset"] && (
                <span className="text-orange-300/60">· {formatClaudeReset(claudeUsage["tokens-reset"])}</span>
              )}
            </div>
          )}
          <button
            onClick={() => setShowPanel(p => !p)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-lg transition-colors
              ${showPanel
                ? "bg-primary/10 border-primary/30 text-primary"
                : "bg-secondary border-border text-muted-foreground hover:text-foreground"}`}
          >
            <MessagesSquare className="w-3.5 h-3.5" />
            Models Talking
          </button>
        </div>
      </div>

      {/* Pending commit approvals */}
      {Object.keys(pendingApprovals).length > 0 && (
        <div className="border-b border-border px-4 py-2 space-y-2 bg-yellow-400/5">
          {Object.entries(pendingApprovals).map(([taskId, info]) => (
            <ApprovalCard
              key={taskId}
              taskId={taskId}
              info={info}
              onApprove={handleApprove}
              onDecline={handleDecline}
            />
          ))}
        </div>
      )}

      {/* Main content — chat + optional conversation panel */}
      <div className="flex flex-1 min-h-0">

        {/* ── Chat area ──────────────────────────────────────────────────────── */}
        <div className={`flex flex-col min-h-0 ${showPanel ? "w-[55%] border-r border-border" : "flex-1"}`}>
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                {m.role === "event" ? (
                  <div className="flex items-start gap-2 text-xs text-muted-foreground bg-secondary/50 rounded px-3 py-2 max-w-2xl">
                    <Zap className="w-3 h-3 mt-0.5 text-primary shrink-0" />
                    <span>{m.content}</span>
                    <span className="ml-auto pl-2 shrink-0">{m.time}</span>
                  </div>
                ) : (
                  <>
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0
                      ${m.role === "assistant" ? "bg-primary/20 text-primary" : "bg-secondary text-foreground"}`}>
                      {m.role === "assistant" ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
                    </div>
                    <div className={`max-w-2xl rounded-2xl px-4 py-3 text-sm
                      ${m.role === "assistant" ? "bg-card text-foreground" : "bg-primary/20 text-foreground"}`}>
                      {m.model && <p className="text-[10px] text-muted-foreground mb-1 font-mono">{m.model}</p>}
                      <p className="whitespace-pre-wrap">{m.content}</p>
                      <p className="text-xs text-muted-foreground mt-1">{m.time}</p>
                    </div>
                  </>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="bg-card rounded-2xl px-4 py-3 flex gap-1 items-center">
                  {[0,1,2].map(d => (
                    <span key={d} className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: `${d * 150}ms` }} />
                  ))}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="p-4 border-t border-border">
            <div className="flex gap-3 bg-card rounded-xl border border-border px-4 py-2">
              <input
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                placeholder={selected ? `Message ${selected.label}…` : "Message Heimdall PM…"}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
              />
              <button onClick={send} disabled={!input.trim() || loading}
                className="text-primary disabled:text-muted-foreground transition-colors">
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* ── Agent conversation panel ────────────────────────────────────────── */}
        {showPanel && (
          <div className="w-[45%] flex flex-col min-h-0 bg-background">
            {/* Panel header */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
              <MessagesSquare className="w-4 h-4 text-primary" />
              <span className="text-sm font-semibold">Models Talking</span>
              <span className="text-xs text-muted-foreground">
                {conversation.length} messages
              </span>
              <div className="ml-auto flex items-center gap-2">
                <button onClick={loadConversation} disabled={convLoading}
                  className="text-muted-foreground hover:text-foreground transition-colors">
                  <RefreshCw className={`w-3.5 h-3.5 ${convLoading ? "animate-spin" : ""}`} />
                </button>
                <button onClick={() => setShowPanel(false)}
                  className="text-muted-foreground hover:text-foreground transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Legend */}
            <div className="flex items-center gap-4 px-4 py-2 border-b border-border shrink-0 bg-card/30">
              {[
                { agent: "pm", label: "PM (Gemma)" },
                { agent: "worker", label: "Worker (Qwen)" },
                { agent: "reviewer", label: "Reviewer (Claude)" },
              ].map(({ agent, label }) => {
                const c = AGENT_COLORS[agent];
                return (
                  <div key={agent} className="flex items-center gap-1.5">
                    <div className={`w-2 h-2 rounded-full ${c.dot}`} />
                    <span className={`text-[10px] font-medium ${c.text}`}>{label}</span>
                  </div>
                );
              })}
            </div>

            {/* Session stats */}
            {Object.keys(sessionStats).length > 0 && (
              <div className="px-4 py-2 border-b border-border bg-card/20 space-y-1">
                {Object.entries(sessionStats).map(([key, s]) => (
                  <div key={key} className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
                    <span className="text-foreground/50 truncate max-w-[160px]">{key}</span>
                    <span className="shrink-0">{s.calls} call{s.calls !== 1 ? "s" : ""}</span>
                    <span>·</span>
                    <span className="shrink-0">{((s.input_tokens + s.output_tokens) / 1000).toFixed(1)}k tok</span>
                    <span>·</span>
                    <span className="shrink-0">avg {s.calls > 0 ? (s.total_ms / s.calls / 1000).toFixed(1) : "0"}s</span>
                  </div>
                ))}
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {convLoading && conversation.length === 0 && (
                <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
                  <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading…
                </div>
              )}
              {!convLoading && conversation.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center space-y-2">
                  <MessagesSquare className="w-8 h-8 text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">No agent conversation yet.</p>
                  <p className="text-xs text-muted-foreground">Start the PM and assign a task to see the models talking.</p>
                </div>
              )}
              {conversation.map((entry, i) => (
                <AgentBubble
                  key={i}
                  entry={entry}
                  expanded={!!expanded[i]}
                  onToggle={() => setExpanded(p => ({ ...p, [i]: !p[i] }))}
                />
              ))}
              {pendingCall && (
                <div className="rounded-xl border border-blue-400/20 bg-blue-400/5 p-3 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse shrink-0" />
                  <span className="text-xs text-blue-400 animate-pulse">
                    {pendingCall.agent === "reviewer" ? "Reviewer (Claude)" : "Worker"} calling {pendingCall.provider}/{pendingCall.model}…
                  </span>
                </div>
              )}
              <div ref={convBottomRef} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
