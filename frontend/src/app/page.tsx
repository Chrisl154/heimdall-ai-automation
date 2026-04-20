"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { api, ConversationEntry, ModelsResponse, PipelineEvent, subscribeToEvents } from "@/lib/api";
import { PMStatusBar } from "@/components/PMStatusBar";
import { Send, Bot, User, Zap, ChevronDown, MessagesSquare, X, ChevronRight, RefreshCw } from "lucide-react";

interface Message { role: "user" | "assistant" | "event"; content: string; time: string; model?: string; }
interface SelectedModel { provider: string; model: string; label: string; }

function now() { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

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
  const [showPanel, setShowPanel]     = useState(false);
  const [conversation, setConversation] = useState<ConversationEntry[]>([]);
  const [convLoading, setConvLoading] = useState(false);
  const [expanded, setExpanded]       = useState<Record<number, boolean>>({});

  const bottomRef   = useRef<HTMLDivElement>(null);
  const convBottomRef = useRef<HTMLDivElement>(null);
  const selectorRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => { convBottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [conversation]);

  useEffect(() => { api.models.scan().then(setModelsData).catch(() => {}); }, []);

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
      if (ev.message) {
        setMessages(prev => [...prev, { role: "event", content: ev.message, time: now() }]);
      }
      // Reload conversation log when workflow events arrive
      const workflowTypes = ["worker_output_received", "review_approved", "review_rejected", "task_completed", "task_escalated"];
      if (workflowTypes.includes(ev.type) && showPanel) {
        loadConversation();
      }
    });
    return unsub;
  }, [showPanel, loadConversation]);

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

        <div className="ml-auto">
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
              <div ref={convBottomRef} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
