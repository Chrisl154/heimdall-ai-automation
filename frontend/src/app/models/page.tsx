"use client";
import { useEffect, useState, useCallback } from "react";
import { api, ModelsResponse, ProviderInfo, AgentsConfig } from "@/lib/api";
import {
  RefreshCw, ChevronDown, ChevronRight, CheckCircle2,
  XCircle, AlertCircle, ExternalLink, Server, Cloud,
  Cpu, Zap, KeyRound, Loader2,
} from "lucide-react";

const PROVIDER_ORDER = ["ollama", "lmstudio", "anthropic", "openai", "grok", "deepseek"];

const PROVIDER_COLORS: Record<string, string> = {
  ollama:    "text-emerald-400",
  lmstudio:  "text-violet-400",
  anthropic: "text-orange-400",
  openai:    "text-blue-400",
  grok:      "text-cyan-400",
  deepseek:  "text-indigo-400",
};

const PROVIDER_BG: Record<string, string> = {
  ollama:    "bg-emerald-400/10 border-emerald-400/20",
  lmstudio:  "bg-violet-400/10 border-violet-400/20",
  anthropic: "bg-orange-400/10 border-orange-400/20",
  openai:    "bg-blue-400/10 border-blue-400/20",
  grok:      "bg-cyan-400/10 border-cyan-400/20",
  deepseek:  "bg-indigo-400/10 border-indigo-400/20",
};

const AGENT_LABELS: Record<string, string> = {
  worker:       "Worker",
  reviewer:     "Reviewer",
  orchestrator: "Orchestrator",
};

const AGENT_DESC: Record<string, string> = {
  worker:       "Executes tasks",
  reviewer:     "Reviews & audits output",
  orchestrator: "Plans & assigns work",
};

export default function ModelsPage() {
  const [data, setData]         = useState<ModelsResponse | null>(null);
  const [agents, setAgents]     = useState<AgentsConfig | null>(null);
  const [loading, setLoading]   = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [saving, setSaving]     = useState<Record<string, boolean>>({});
  const [saved, setSaved]       = useState<Record<string, boolean>>({});
  const [drafts, setDrafts]     = useState<Record<string, { provider: string; model: string }>>({});
  const [error, setError]       = useState("");
  const [connecting, setConnecting]   = useState<Record<string, boolean>>({});
  const [draftKey, setDraftKey]       = useState<Record<string, string>>({});
  const [validating, setValidating]   = useState<Record<string, boolean>>({});
  const [connectErr, setConnectErr]   = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [m, a] = await Promise.all([api.models.scan(), api.config.agents()]);
      setData(m);
      setAgents(a);
      setDrafts({
        worker:       { provider: a.worker.provider,       model: a.worker.model },
        reviewer:     { provider: a.reviewer.provider,     model: a.reviewer.model },
        orchestrator: { provider: a.orchestrator.provider, model: a.orchestrator.model },
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = (key: string) =>
    setExpanded(p => ({ ...p, [key]: !p[key] }));

  const saveAgent = async (name: string) => {
    const draft = drafts[name];
    if (!draft) return;
    setSaving(p => ({ ...p, [name]: true }));
    try {
      const provider = data?.providers[draft.provider];
      await api.config.updateAgent(name, {
        provider: draft.provider,
        model: draft.model,
        base_url: provider?.base_url ?? undefined,
      });
      setSaved(p => ({ ...p, [name]: true }));
      setTimeout(() => setSaved(p => ({ ...p, [name]: false })), 2000);
      await load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Save failed");
    }
    setSaving(p => ({ ...p, [name]: false }));
  };

  const connectProvider = async (key: string) => {
    const apiKey = draftKey[key]?.trim();
    if (!apiKey) return;
    setValidating(p => ({ ...p, [key]: true }));
    setConnectErr(p => ({ ...p, [key]: "" }));
    try {
      const res = await api.models.validateKey(key, apiKey);
      if (res.valid) {
        setConnecting(p => ({ ...p, [key]: false }));
        setDraftKey(p => ({ ...p, [key]: "" }));
        await load();
      } else {
        setConnectErr(p => ({ ...p, [key]: res.error ?? "Invalid API key" }));
      }
    } catch (e: unknown) {
      setConnectErr(p => ({ ...p, [key]: e instanceof Error ? e.message : "Validation failed" }));
    }
    setValidating(p => ({ ...p, [key]: false }));
  };

  const availableModels = data
    ? data.all_models
    : [];

  const statusIcon = (p: ProviderInfo) => {
    if (p.no_key)    return <AlertCircle className="w-3.5 h-3.5 text-yellow-400" />;
    if (p.available) return <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />;
    return <XCircle className="w-3.5 h-3.5 text-red-400" />;
  };

  const statusLabel = (p: ProviderInfo) => {
    if (p.no_key)    return "No API key";
    if (p.available) return `${p.models.length} model${p.models.length !== 1 ? "s" : ""}`;
    return p.type === "local" ? "Not reachable" : "Not configured";
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex items-center gap-3 text-muted-foreground">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Scanning providers…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto w-full">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Models</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Configure which AI models power each agent
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-secondary border border-border rounded-lg hover:bg-secondary/70 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Rescan
        </button>
      </div>

      {error && (
        <div className="bg-red-400/10 border border-red-400/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Agent Assignment */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
          Agent Configuration
        </h2>
        <div className="grid grid-cols-1 gap-3">
          {(["worker", "reviewer", "orchestrator"] as const).map(agent => {
            const draft = drafts[agent];
            const current = agents?.[agent];
            const dirty =
              draft &&
              (draft.provider !== current?.provider || draft.model !== current?.model);
            return (
              <div key={agent} className="bg-card border border-border rounded-xl p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-primary shrink-0" />
                      <span className="font-medium text-sm">{AGENT_LABELS[agent]}</span>
                      <span className="text-xs text-muted-foreground">— {AGENT_DESC[agent]}</span>
                    </div>
                    {current && (
                      <p className="text-xs text-muted-foreground mt-1 font-mono">
                        {current.provider} / {current.model || "not set"}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {dirty && (
                      <button
                        onClick={() => saveAgent(agent)}
                        disabled={saving[agent]}
                        className="px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-lg hover:bg-primary/80 disabled:opacity-50 transition-colors"
                      >
                        {saving[agent] ? "Saving…" : saved[agent] ? "Saved ✓" : "Save"}
                      </button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 mt-3">
                  {/* Provider picker */}
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Provider</label>
                    <select
                      value={draft?.provider ?? ""}
                      onChange={e => setDrafts(p => ({
                        ...p,
                        [agent]: { provider: e.target.value, model: "" },
                      }))}
                      className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="">Select provider…</option>
                      {data && PROVIDER_ORDER.map(key => {
                        const prov = data.providers[key];
                        if (!prov) return null;
                        return (
                          <option key={key} value={key}>
                            {prov.label} {!prov.available ? "(offline)" : `(${prov.models.length})`}
                          </option>
                        );
                      })}
                    </select>
                  </div>

                  {/* Model picker */}
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Model</label>
                    <select
                      value={draft?.model ?? ""}
                      onChange={e => setDrafts(p => ({
                        ...p,
                        [agent]: { ...p[agent], model: e.target.value },
                      }))}
                      className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                      disabled={!draft?.provider}
                    >
                      <option value="">Select model…</option>
                      {data && draft?.provider &&
                        (data.providers[draft.provider]?.models ?? []).map(m => (
                          <option key={m} value={m}>{m}</option>
                        ))
                      }
                    </select>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Provider Cards */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
          Providers
        </h2>
        <div className="space-y-2">
          {data && PROVIDER_ORDER.map(key => {
            const prov = data.providers[key];
            if (!prov) return null;
            const open = expanded[key];
            const color = PROVIDER_COLORS[key] ?? "text-muted-foreground";
            const bg    = PROVIDER_BG[key]    ?? "bg-secondary border-border";
            return (
              <div key={key} className="bg-card border border-border rounded-xl overflow-hidden">
                {/* Card header */}
                <button
                  onClick={() => toggle(key)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-secondary/30 transition-colors text-left"
                >
                  <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 ${bg}`}>
                    {prov.type === "local"
                      ? <Server className={`w-4 h-4 ${color}`} />
                      : <Cloud className={`w-4 h-4 ${color}`} />
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{prov.label}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full border ${bg} ${color}`}>
                        {prov.type}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{prov.description}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {statusIcon(prov)}
                    <span className="text-xs text-muted-foreground">{statusLabel(prov)}</span>
                    {open ? <ChevronDown className="w-4 h-4 text-muted-foreground" /> : <ChevronRight className="w-4 h-4 text-muted-foreground" />}
                  </div>
                </button>

                {/* Expanded content */}
                {open && (
                  <div className="border-t border-border px-4 py-3 space-y-3">
                    {/* Local URL */}
                    {prov.type === "local" && (
                      <div>
                        <label className="text-xs text-muted-foreground mb-1 block">Base URL</label>
                        <div className="flex items-center gap-2">
                          <code className="flex-1 bg-background border border-border rounded-lg px-3 py-2 text-xs font-mono text-muted-foreground">
                            {prov.base_url}
                          </code>
                          <span className="text-xs text-muted-foreground">
                            (edit in Settings → Providers)
                          </span>
                        </div>
                      </div>
                    )}

                    {/* No key — Connect form for cloud providers */}
                    {prov.no_key && prov.type === "cloud" && (
                      <div className="space-y-2">
                        {!connecting[key] ? (
                          <div className="flex items-center gap-3">
                            <div className="flex items-center gap-2 text-xs text-yellow-400">
                              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                              No API key configured.
                            </div>
                            {prov.key_url && (
                              <a href={prov.key_url} target="_blank" rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                                Get key <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                            <button
                              onClick={() => setConnecting(p => ({ ...p, [key]: true }))}
                              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-lg hover:bg-primary/80 transition-colors"
                            >
                              <KeyRound className="w-3 h-3" /> Connect
                            </button>
                          </div>
                        ) : (
                          <div className="bg-yellow-400/5 border border-yellow-400/20 rounded-lg p-3 space-y-2">
                            <p className="text-xs text-yellow-400 font-medium">Connect {prov.label}</p>
                            {prov.key_url && (
                              <a href={prov.key_url} target="_blank" rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                                Get your API key from {prov.label} <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                            <input
                              type="password"
                              placeholder={`Paste your ${prov.key_name ?? "api_key"} here…`}
                              value={draftKey[key] ?? ""}
                              onChange={e => setDraftKey(p => ({ ...p, [key]: e.target.value }))}
                              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                            {connectErr[key] && (
                              <p className="text-xs text-red-400">{connectErr[key]}</p>
                            )}
                            <div className="flex gap-2">
                              <button
                                onClick={() => connectProvider(key)}
                                disabled={!draftKey[key]?.trim() || validating[key]}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-lg hover:bg-primary/80 disabled:opacity-50 transition-colors"
                              >
                                {validating[key] ? <><Loader2 className="w-3 h-3 animate-spin" /> Validating…</> : "Validate & Connect"}
                              </button>
                              <button
                                onClick={() => { setConnecting(p => ({ ...p, [key]: false })); setConnectErr(p => ({ ...p, [key]: "" })); }}
                                className="px-3 py-1.5 text-xs bg-secondary border border-border rounded-lg hover:bg-secondary/70 transition-colors"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Not reachable for local */}
                    {!prov.available && prov.type === "local" && (
                      <div className="flex items-center gap-2 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
                        <XCircle className="w-4 h-4 text-red-400 shrink-0" />
                        <p className="text-xs text-red-400">
                          {key === "ollama" ? "Ollama is not running. Start it with: ollama serve" : "LM Studio server is not running. Start it from the LM Studio app."}
                        </p>
                      </div>
                    )}

                    {/* Model list */}
                    {prov.models.length > 0 && (
                      <div>
                        <label className="text-xs text-muted-foreground mb-2 block">
                          Available Models ({prov.models.length})
                        </label>
                        <div className="grid grid-cols-2 gap-1 max-h-48 overflow-y-auto">
                          {prov.models.map(m => {
                            const inUse = availableModels.some(
                              am => am.provider === key && am.model === m
                                && Object.values(drafts).some(d => d.provider === key && d.model === m)
                            );
                            return (
                              <div
                                key={m}
                                className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-background border border-border text-xs font-mono group"
                              >
                                <Zap className={`w-3 h-3 shrink-0 ${inUse ? color : "text-muted-foreground"}`} />
                                <span className="truncate text-foreground/80">{m}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
