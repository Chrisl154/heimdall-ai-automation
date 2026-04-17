"use client";
import { useEffect, useRef, useState } from "react";
import { api, PipelineEvent, subscribeToEvents } from "@/lib/api";
import { PMStatusBar } from "@/components/PMStatusBar";
import { Send, Bot, User, Zap } from "lucide-react";

interface Message { role: "user" | "assistant" | "event"; content: string; time: string; }

function now() { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hello! I'm Heimdall, your AI Project Manager. You can ask me about task status, start/stop the pipeline, or give me new tasks.", time: now() },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const unsub = subscribeToEvents((ev: PipelineEvent) => {
      if (!ev.message) return;
      setMessages(prev => [...prev, { role: "event", content: ev.message, time: now() }]);
    });
    return unsub;
  }, []);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: text, time: now() }]);
    setLoading(true);
    try {
      const res = await api.pm.chat(text);
      setMessages(prev => [...prev, { role: "assistant", content: res.reply, time: now() }]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${msg}`, time: now() }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <PMStatusBar />
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
            placeholder="Message Heimdall PM…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
          />
          <button
            onClick={send}
            disabled={!input.trim() || loading}
            className="text-primary disabled:text-muted-foreground transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
