"use client";
import { useEffect, useState } from "react";
import { api, MessagingChannel, WebhookConfig, AgentConfig, AgentsConfig } from "@/lib/api";
import { Lock, Unlock, Save, Plus, Trash2, ToggleLeft, ToggleRight, Send, RefreshCw, Download, CheckCircle2, XCircle, RotateCcw } from "lucide-react";
import { SystemInfo } from "@/lib/api";

type Tab = "providers" | "vault" | "channels" | "webhooks" | "restrictions" | "system";
type ChannelType = "telegram" | "discord" | "email";

const PROVIDER_KEYS = [
  { key: "anthropic_key", label: "Anthropic (Claude)", provider: "anthropic" },
  { key: "openai_key", label: "OpenAI / Codex", provider: "openai" },
  { key: "github_token", label: "GitHub PAT", provider: "github" },
];

const CHANNEL_CREDENTIAL_FIELDS: Record<ChannelType, { key: string; label: string; secret?: boolean }[]> = {
  telegram: [
    { key: "bot_token", label: "Bot Token", secret: true },
  ],
  discord: [
    { key: "bot_token", label: "Bot Token", secret: true },
  ],
  email: [
    { key: "smtp_host", label: "SMTP Host" },
    { key: "smtp_port", label: "SMTP Port" },
    { key: "smtp_user", label: "SMTP User" },
    { key: "smtp_password", label: "SMTP Password", secret: true },
    { key: "imap_host", label: "IMAP Host" },
    { key: "imap_port", label: "IMAP Port" },
    { key: "imap_user", label: "IMAP User" },
    { key: "imap_password", label: "IMAP Password", secret: true },
    { key: "from_address", label: "From Address" },
    { key: "command_subject_prefix", label: "Command Subject Prefix" },
  ],
};

const TYPE_LABELS: Record<ChannelType, string> = {
  telegram: "Telegram",
  discord: "Discord",
  email: "Email",
};

const AGENT_LABELS: Record<string, string> = {
  worker: "Worker",
  reviewer: "Reviewer",
  orchestrator: "Orchestrator",
};

const CLOUD_PROVIDERS = ["anthropic", "openai", "grok", "deepseek"];
const ALL_PROVIDERS = ["anthropic", "openai", "grok", "deepseek", "ollama", "lmstudio"];

const CLOUD_MODEL_SUGGESTIONS: Record<string, string[]> = {
  anthropic: ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"],
  grok: ["grok-3", "grok-3-mini", "grok-2"],
  deepseek: ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
};

const WEBHOOK_EVENTS = [
  "task_completed", "task_escalated", "task_failed",
  "task_started", "review_approved", "review_rejected",
];

interface AddChannelForm {
  type: ChannelType;
  name: string;
  targets: string;
  credentials: Record<string, string>;
}

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("providers");

  // ── Vault state ──────────────────────────────────────────────────────────────
  const [vaultKeys, setVaultKeys] = useState<string[]>([]);
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});

  const refreshKeys = () =>
    api.vault.keys().then(r => setVaultKeys(r.keys)).catch(() => { });

  useEffect(() => { refreshKeys(); }, []);

  const saveKey = async (key: string) => {
    const val = keyInputs[key];
    if (!val) return;
    setSaving(s => ({ ...s, [key]: true }));
    await api.vault.set(key, val).catch(() => { });
    setKeyInputs(s => ({ ...s, [key]: "" }));
    await refreshKeys();
    setSaving(s => ({ ...s, [key]: false }));
  };

  const deleteKey = async (key: string) => {
    await api.vault.delete(key).catch(() => { });
    await refreshKeys();
  };

  // ── Agent config state ───────────────────────────────────────────────────────
  const [agentsConfig, setAgentsConfig] = useState<AgentsConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [savingAgent, setSavingAgent] = useState<Record<string, boolean>>({});
  const [savedAgent, setSavedAgent] = useState<string | null>(null);
  const [agentEdits, setAgentEdits] = useState<Record<string, { model: string; base_url: string; provider: string }>>({});
  const [detectedModels, setDetectedModels] = useState<Record<string, string[]>>({});
  const [scanning, setScanning] = useState<Record<string, boolean>>({});

  const refreshConfig = async () => {
    setConfigLoading(true);
    try {
      const cfg = await api.config.agents();
      setAgentsConfig(cfg);
      const edits: Record<string, { model: string; base_url: string; provider: string }> = {};
      for (const [name, c] of Object.entries(cfg as AgentsConfig)) {
        edits[name] = { model: "", base_url: (c as AgentConfig).base_url ?? "", provider: (c as AgentConfig).provider ?? "" };
      }
      setAgentEdits(edits);
    } catch { }
    setConfigLoading(false);
  };

  const scanAgentModels = async (name: string) => {
    const baseUrl = agentEdits[name]?.base_url?.trim();
    const provider = agentEdits[name]?.provider;
    if (!baseUrl || !provider) return;
    setScanning(s => ({ ...s, [name]: true }));
    setDetectedModels(d => ({ ...d, [name]: [] }));
    try {
      const res = await api.models.probe(provider, baseUrl);
      if (res.available && res.models?.length) {
        setDetectedModels(d => ({ ...d, [name]: res.models }));
      } else {
        setDetectedModels(d => ({ ...d, [name]: [] }));
        alert(`No models found at ${baseUrl}. Make sure the service is running and the URL is correct.`);
      }
    } catch (e: unknown) {
      alert(`Scan failed: ${e instanceof Error ? e.message : "Could not reach provider"}`);
    }
    setScanning(s => ({ ...s, [name]: false }));
  };

  useEffect(() => {
    if (tab === "providers") refreshConfig();
  }, [tab]);

  const saveAgentConfig = async (name: string) => {
    const edits = agentEdits[name];
    if (!edits) return;
    setSavingAgent(s => ({ ...s, [name]: true }));
    try {
      await api.config.updateAgent(name, {
        model: edits.model,
        provider: edits.provider || undefined,
        base_url: CLOUD_PROVIDERS.includes(edits.provider) ? undefined : (edits.base_url || undefined),
      });
      setSavedAgent(name);
      setTimeout(() => setSavedAgent(null), 2000);
      await refreshConfig();
    } catch (e: unknown) {
      alert(`Error: ${e instanceof Error ? e.message : "Save failed"}`);
    }
    setSavingAgent(s => ({ ...s, [name]: false }));
  };

  // ── System / update state ────────────────────────────────────────────────────
  const [sysInfo, setSysInfo]         = useState<SystemInfo | null>(null);
  const [sysLoading, setSysLoading]   = useState(false);
  const [updateLog, setUpdateLog]     = useState<{ type: string; message: string }[]>([]);
  const [updating, setUpdating]       = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [updateDone, setUpdateDone]   = useState(false);
  const [updateError, setUpdateError] = useState("");

  const loadSysInfo = async () => {
    setSysLoading(true);
    try { setSysInfo(await api.system.info()); } catch { /* ignore */ }
    setSysLoading(false);
  };

  useEffect(() => { if (tab === "system") loadSysInfo(); }, [tab]);

  const startUpdate = async () => {
    setUpdating(true);
    setUpdateLog([]);
    setUpdateDone(false);
    setUpdateError("");
    setReconnecting(false);

    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
      const token = localStorage.getItem("heimdall_token") ?? "";
      const res = await fetch(`${BASE}/api/system/update`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`);

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const dataLine = part.split("\n").find(l => l.startsWith("data: "));
          if (!dataLine) continue;
          try {
            const ev = JSON.parse(dataLine.slice(6));
            setUpdateLog(p => [...p, ev]);
            if (ev.type === "restarting") {
              setReconnecting(true);
              // Poll /api/health until it responds
              const poll = setInterval(async () => {
                try {
                  const h = await fetch(`${BASE}/api/health`);
                  if (h.ok) {
                    clearInterval(poll);
                    setReconnecting(false);
                    setUpdateDone(true);
                    setUpdating(false);
                    loadSysInfo();
                  }
                } catch { /* still down */ }
              }, 2000);
            }
            if (ev.type === "done") {
              setUpdateDone(true);
              setUpdating(false);
              loadSysInfo();
            }
            if (ev.type === "error") {
              setUpdateError(ev.message);
              setUpdating(false);
            }
          } catch { /* bad JSON line */ }
        }
      }
    } catch (e: unknown) {
      if (!reconnecting) {
        setUpdateError(e instanceof Error ? e.message : "Update failed");
        setUpdating(false);
      }
    }
  };

  // ── Restrictions state ───────────────────────────────────────────────────────
  const [restrictionsText, setRestrictionsText] = useState("");
  const [restrictionsDirty, setRestrictionsDirty] = useState(false);
  const [savingRestrictions, setSavingRestrictions] = useState(false);
  const [restrictionsError, setRestrictionsError] = useState("");

  useEffect(() => {
    if (tab === "restrictions" && !restrictionsText) {
      api.restrictions.get().then(data => {
        setRestrictionsText(data);
      }).catch(() => { });
    }
  }, [tab]);

  const saveRestrictions = async () => {
    setSavingRestrictions(true);
    setRestrictionsError("");
    try {
      await api.restrictions.update(restrictionsText);
      setRestrictionsDirty(false);
    } catch (e: unknown) {
      setRestrictionsError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSavingRestrictions(false);
    }
  };

  // ── Channels state ───────────────────────────────────────────────────────────
  const [channels, setChannels] = useState<MessagingChannel[]>([]);
  const [channelsLoading, setChannelsLoading] = useState(false);
  const [showAddChannelModal, setShowAddChannelModal] = useState(false);
  const [addChannelForm, setAddChannelForm] = useState<AddChannelForm>({
    type: "telegram",
    name: "",
    targets: "",
    credentials: {},
  });
  const [addChannelSaving, setAddChannelSaving] = useState(false);

  const refreshChannels = async () => {
    setChannelsLoading(true);
    try {
      const list = await api.messaging.channels();
      setChannels(list);
    } catch { }
    setChannelsLoading(false);
  };

  useEffect(() => {
    if (tab === "channels") refreshChannels();
  }, [tab]);

  const toggleChannel = async (ch: MessagingChannel) => {
    await api.messaging.updateChannel(ch.id, { enabled: !ch.enabled }).catch(() => { });
    await refreshChannels();
  };

  const deleteChannel = async (id: string) => {
    await api.messaging.deleteChannel(id).catch(() => { });
    await refreshChannels();
  };

  const openAddChannelModal = () => {
    setAddChannelForm({ type: "telegram", name: "", targets: "", credentials: {} });
    setShowAddChannelModal(true);
  };

  const submitAddChannel = async () => {
    if (!addChannelForm.name) return;
    setAddChannelSaving(true);
    try {
      const targets = addChannelForm.targets.split(/[\n,]+/).map((s: string) => s.trim()).filter(Boolean);
      await api.messaging.addChannel({
        type: addChannelForm.type,
        name: addChannelForm.name,
        targets,
        credentials: addChannelForm.credentials,
      });
      setShowAddChannelModal(false);
      await refreshChannels();
    } catch { }
    setAddChannelSaving(false);
  };

  // ── Webhooks state ───────────────────────────────────────────────────────────
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [webhooksLoading, setWebhooksLoading] = useState(false);
  const [showAddWebhookModal, setShowAddWebhookModal] = useState(false);
  const [addWebhookForm, setAddWebhookForm] = useState({
    url: "", secret: "", events: [] as string[], enabled: true,
  });
  const [savingWebhook, setSavingWebhook] = useState(false);

  const refreshWebhooks = async () => {
    setWebhooksLoading(true);
    try {
      const res = await api.webhooks.list();
      setWebhooks(res.webhooks);
    } catch { }
    setWebhooksLoading(false);
  };

  useEffect(() => {
    if (tab === "webhooks") refreshWebhooks();
  }, [tab]);

  const deleteWebhook = async (index: number) => {
    await api.webhooks.remove(index).catch(() => { });
    await refreshWebhooks();
  };

  const testWebhook = async (index: number, url: string) => {
    try {
      await api.webhooks.test(index);
      alert(`Test sent to ${url}`);
    } catch (e: unknown) {
      alert(`Error: ${e instanceof Error ? e.message : "Test failed"}`);
    }
  };

  const submitAddWebhook = async () => {
    if (!addWebhookForm.url) return;
    setSavingWebhook(true);
    try {
      await api.webhooks.add({
        url: addWebhookForm.url,
        secret: addWebhookForm.secret,
        events: addWebhookForm.events,
        enabled: addWebhookForm.enabled,
      });
      setShowAddWebhookModal(false);
      await refreshWebhooks();
    } catch (e: unknown) {
      alert(`Error: ${e instanceof Error ? e.message : "Add failed"}`);
    }
    setSavingWebhook(false);
  };

  const TABS: { id: Tab; label: string }[] = [
    { id: "providers", label: "AI Providers" },
    { id: "vault", label: "Vault" },
    { id: "channels", label: "Channels" },
    { id: "webhooks", label: "Webhooks" },
    { id: "restrictions", label: "Restrictions" },
    { id: "system", label: "System" },
  ];

  return (
    <div className="p-6 overflow-y-auto h-full space-y-4">
      <h1 className="text-lg font-semibold">Settings</h1>

      {/* Tab bar */}
      <div className="flex gap-1 bg-secondary rounded-lg p-1 w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-1.5 rounded-md text-sm transition-colors ${tab === t.id ? "bg-card text-foreground shadow" : "text-muted-foreground hover:text-foreground"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Providers tab ─────────────────────────────────────────────────────── */}
      {tab === "providers" && (
        <div className="space-y-3">
          {/* Agent config cards */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-foreground">Agent Configuration</h3>
            {configLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
             {!configLoading && agentsConfig && Object.entries(agentsConfig).map(([name, cfg]) => {
              const agentConfig = cfg as AgentConfig;
              if (!agentConfig || typeof agentConfig !== "object") return null;
              const savedModel = agentConfig.model ?? "";
              const editProvider = agentEdits[name]?.provider ?? agentConfig.provider ?? "";
              const isCloud = CLOUD_PROVIDERS.includes(editProvider);
              const isLocal = !isCloud && !!editProvider;
              const suggestions = CLOUD_MODEL_SUGGESTIONS[editProvider] ?? [];
              const listId = `models-${name}`;
              return (
                <div key={name} className="bg-card rounded-xl border border-border p-4">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium">{AGENT_LABELS[name] ?? name}</p>
                    {savedAgent === name && <span className="text-xs text-green-400">Saved!</span>}
                  </div>
                  <div className="space-y-2">
                    {savedModel && (
                      <p className="text-xs text-muted-foreground">
                        Current: <span className="font-mono text-foreground/70">{savedModel}</span>
                        {agentConfig.provider && <span className="ml-2 bg-secondary px-1.5 py-0.5 rounded">{agentConfig.provider}</span>}
                      </p>
                    )}

                    {/* Provider selector */}
                    <div>
                      <label className="text-xs text-muted-foreground block mb-1">Provider</label>
                      <select
                        value={editProvider}
                        onChange={e => setAgentEdits(ed => ({ ...ed, [name]: { ...ed[name], provider: e.target.value, model: "", base_url: ed[name]?.base_url ?? "" } }))}
                        className="w-full px-3 py-1.5 bg-input border border-border rounded text-sm outline-none focus:border-primary"
                      >
                        <option value="">Select provider…</option>
                        {ALL_PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </div>

                    {/* Local: Base URL + Scan */}
                    {isLocal && (
                      <div>
                        <label className="text-xs text-muted-foreground block mb-1">Base URL</label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={agentEdits[name]?.base_url ?? ""}
                            onChange={e => setAgentEdits(ed => ({ ...ed, [name]: { ...ed[name], base_url: e.target.value } }))}
                            className="flex-1 px-3 py-1.5 bg-input border border-border rounded text-sm outline-none focus:border-primary"
                            placeholder={editProvider === "ollama" ? "http://127.0.0.1:11434" : "http://127.0.0.1:1234"}
                          />
                          <button
                            onClick={() => scanAgentModels(name)}
                            disabled={scanning[name] || !agentEdits[name]?.base_url}
                            className="flex items-center gap-1 px-3 py-1.5 bg-secondary border border-border rounded text-xs hover:bg-secondary/70 disabled:opacity-40 transition-colors shrink-0"
                          >
                            <RefreshCw className={`w-3 h-3 ${scanning[name] ? "animate-spin" : ""}`} />
                            {scanning[name] ? "Scanning…" : "Scan"}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Model input */}
                    {editProvider && (
                      <div>
                        <label className="text-xs text-muted-foreground block mb-1">Model</label>
                        {isCloud ? (
                          <>
                            <input
                              list={listId}
                              type="text"
                              value={agentEdits[name]?.model ?? ""}
                              onChange={e => setAgentEdits(ed => ({ ...ed, [name]: { ...ed[name], model: e.target.value } }))}
                              className="w-full px-3 py-1.5 bg-input border border-border rounded text-sm outline-none focus:border-primary"
                              placeholder="Type or pick a model…"
                            />
                            <datalist id={listId}>
                              {suggestions.map(m => <option key={m} value={m} />)}
                            </datalist>
                          </>
                        ) : detectedModels[name]?.length > 0 ? (
                          <select
                            value={agentEdits[name]?.model ?? ""}
                            onChange={e => setAgentEdits(ed => ({ ...ed, [name]: { ...ed[name], model: e.target.value } }))}
                            className="w-full px-3 py-1.5 bg-input border border-border rounded text-sm outline-none focus:border-primary"
                          >
                            <option value="">Select a model…</option>
                            {detectedModels[name].map(m => <option key={m} value={m}>{m}</option>)}
                          </select>
                        ) : (
                          <div className="w-full px-3 py-1.5 bg-input border border-border rounded text-sm text-muted-foreground italic">
                            {scanning[name] ? "Scanning…" : "Enter Base URL above and click Scan"}
                          </div>
                        )}
                      </div>
                    )}

                    <button
                      onClick={() => saveAgentConfig(name)}
                      disabled={savingAgent[name] || !agentEdits[name]?.model || !editProvider}
                      className="w-full py-1.5 bg-primary/20 text-primary hover:bg-primary/30 rounded text-xs disabled:opacity-40 transition-colors"
                    >
                      {savingAgent[name] ? "Saving…" : "Save"}
                    </button>
                  </div>
                </div>
              );
             })}
          </div>

          {/* API key rows */}
          <h3 className="text-sm font-semibold text-foreground pt-2">API Keys</h3>
          <p className="text-sm text-muted-foreground">
            API keys are stored encrypted in the vault. They are never displayed after saving.
          </p>
          {PROVIDER_KEYS.map(({ key, label }) => {
            const exists = vaultKeys.includes(key);
            return (
              <div key={key} className="bg-card rounded-xl border border-border p-4 flex items-center gap-4">
                <div className="flex-1">
                  <p className="text-sm font-medium">{label}</p>
                  <p className="text-xs text-muted-foreground font-mono">{key}</p>
                </div>
                {exists
                  ? <div className="flex items-center gap-2 text-green-400 text-xs"><Lock className="w-4 h-4" /> Stored</div>
                  : <div className="flex items-center gap-2 text-muted-foreground text-xs"><Unlock className="w-4 h-4" /> Not set</div>
                }
                <input
                  type="password"
                  className="bg-input border border-border rounded-lg px-3 py-1.5 text-sm w-52 outline-none focus:border-primary"
                  placeholder={exists ? "Replace key…" : "Paste key…"}
                  value={keyInputs[key] ?? ""}
                  onChange={e => setKeyInputs(s => ({ ...s, [key]: e.target.value }))}
                />
                <button onClick={() => saveKey(key)} disabled={saving[key] || !keyInputs[key]}
                  className="flex items-center gap-1 text-xs bg-primary/20 text-primary hover:bg-primary/30 px-3 py-1.5 rounded-lg disabled:opacity-40 transition-colors">
                  <Save className="w-3 h-3" /> Save
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Vault tab ─────────────────────────────────────────────────────────── */}
      {tab === "vault" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">All vault keys (values are never shown).</p>
          {vaultKeys.length === 0 && <p className="text-sm text-muted-foreground">Vault is empty.</p>}
          {vaultKeys.map(k => (
            <div key={k} className="bg-card rounded-lg border border-border px-4 py-3 flex items-center justify-between">
              <span className="font-mono text-sm">{k}</span>
              <button onClick={() => deleteKey(k)} className="text-muted-foreground hover:text-destructive transition-colors">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
          <p className="text-xs text-muted-foreground mt-2">Add new keys from the Providers tab or via the API.</p>
        </div>
      )}

      {/* ── Channels tab ──────────────────────────────────────────────────────── */}
      {tab === "channels" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Telegram, Discord, and Email channels. Credentials are stored encrypted in the vault.
            </p>
            <button onClick={openAddChannelModal}
              className="flex items-center gap-1 text-xs bg-primary/20 text-primary hover:bg-primary/30 px-3 py-1.5 rounded-lg transition-colors">
              <Plus className="w-3 h-3" /> Add Channel
            </button>
          </div>

          {channelsLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

          {!channelsLoading && channels.length === 0 && (
            <div className="bg-card rounded-xl border border-border p-6 text-center text-muted-foreground text-sm">
              No channels configured. Add one to enable notifications.
            </div>
          )}

          {channels.map(ch => (
            <div key={ch.id} className="bg-card rounded-xl border border-border p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium">{ch.name}</p>
                  <span className="text-xs bg-secondary px-2 py-0.5 rounded text-muted-foreground">
                    {TYPE_LABELS[ch.type as ChannelType] ?? ch.type}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground font-mono truncate">{ch.id}</p>
                {ch.targets.length > 0 && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Targets: {ch.targets.join(", ")}
                  </p>
                )}
              </div>
              <button onClick={() => toggleChannel(ch)}
                className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${ch.enabled ? "text-green-400 hover:text-green-300" : "text-muted-foreground hover:text-foreground"}`}
                title={ch.enabled ? "Disable" : "Enable"}>
                {ch.enabled ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
                <span>{ch.enabled ? "On" : "Off"}</span>
              </button>
              <button onClick={() => deleteChannel(ch.id)}
                className="text-muted-foreground hover:text-destructive transition-colors">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Webhooks tab ──────────────────────────────────────────────────────── */}
      {tab === "webhooks" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Configure webhook endpoints to receive event notifications.
            </p>
            <button onClick={() => { setAddWebhookForm({ url: "", secret: "", events: [], enabled: true }); setShowAddWebhookModal(true); }}
              className="flex items-center gap-1 text-xs bg-primary/20 text-primary hover:bg-primary/30 px-3 py-1.5 rounded-lg transition-colors">
              <Plus className="w-3 h-3" /> Add Webhook
            </button>
          </div>

          {webhooksLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

          {!webhooksLoading && webhooks.length === 0 && (
            <div className="bg-card rounded-xl border border-border p-6 text-center text-muted-foreground text-sm">
              No webhooks configured. Add one to receive event notifications.
            </div>
          )}

          {webhooks.map((wh, idx) => (
            <div key={idx} className="bg-card rounded-xl border border-border p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium truncate">{wh.url}</p>
                  <span className={`text-xs px-2 py-0.5 rounded ${wh.enabled ? "bg-primary/20 text-primary" : "text-muted-foreground bg-secondary"}`}>
                    {wh.enabled ? "Enabled" : "Disabled"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Events: {wh.events.length > 0 ? wh.events.join(", ") : "none"}
                </p>
              </div>
              <button onClick={() => testWebhook(idx, wh.url)}
                className="text-muted-foreground hover:text-primary transition-colors" title="Send test">
                <Send className="w-4 h-4" />
              </button>
              <button onClick={() => deleteWebhook(idx)}
                className="text-muted-foreground hover:text-destructive transition-colors">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Restrictions tab ─────────────────────────────────────────────────── */}
      {tab === "restrictions" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Edit <span className="font-mono text-xs bg-secondary px-1 rounded">config/restrictions.yaml</span> directly. Changes take effect immediately.
          </p>
          <textarea
            className="w-full h-96 bg-input border border-border rounded-xl px-4 py-3 font-mono text-xs outline-none focus:border-primary resize-y"
            value={restrictionsText}
            onChange={e => { setRestrictionsText(e.target.value); setRestrictionsDirty(true); }}
            spellCheck={false}
          />
          {restrictionsError && (
            <p className="text-xs text-destructive">{restrictionsError}</p>
          )}
          <button
            onClick={saveRestrictions}
            disabled={savingRestrictions || !restrictionsDirty}
            className="flex items-center gap-1 text-xs bg-primary/20 text-primary hover:bg-primary/30 px-4 py-2 rounded-lg disabled:opacity-40 transition-colors"
          >
            <Save className="w-3 h-3" />
            {savingRestrictions ? "Saving…" : "Save Restrictions"}
          </button>
        </div>
      )}

      {/* ── System tab ───────────────────────────────────────────────────────── */}
      {tab === "system" && (
        <div className="space-y-4 max-w-2xl">
          {/* Version card */}
          <div className="bg-card border border-border rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Current Version</h3>
              <button onClick={loadSysInfo} disabled={sysLoading}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-secondary border border-border rounded-lg hover:bg-secondary/70 disabled:opacity-50 transition-colors">
                <RefreshCw className={`w-3.5 h-3.5 ${sysLoading ? "animate-spin" : ""}`} />
                {sysLoading ? "Checking…" : "Check"}
              </button>
            </div>

            {sysInfo ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 font-mono text-sm">
                  <span className="text-primary">{sysInfo.sha}</span>
                  <span className="text-muted-foreground">on</span>
                  <span>{sysInfo.branch}</span>
                </div>
                <p className="text-sm">{sysInfo.message}</p>
                <p className="text-xs text-muted-foreground">
                  {sysInfo.author} · {new Date(sysInfo.date).toLocaleString()}
                </p>
                {sysInfo.commits_behind > 0 ? (
                  <div className="flex items-center gap-2 text-xs text-yellow-400 bg-yellow-400/10 border border-yellow-400/20 rounded-lg px-3 py-2">
                    <Download className="w-3.5 h-3.5 shrink-0" />
                    {sysInfo.commits_behind} commit{sysInfo.commits_behind !== 1 ? "s" : ""} behind remote — update available
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-xs text-green-400">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Up to date
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{sysLoading ? "Fetching version info…" : "Click Check to load version info."}</p>
            )}
          </div>

          {/* Update card */}
          <div className="bg-card border border-border rounded-xl p-4 space-y-3">
            <h3 className="text-sm font-semibold">Update &amp; Restart</h3>
            <p className="text-xs text-muted-foreground">
              Pulls the latest code, rebuilds the frontend, and restarts the service. Your vault, API keys, and config are untouched.
            </p>

            {!updating && !updateDone && !reconnecting && (
              <button
                onClick={startUpdate}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/80 transition-colors"
              >
                <Download className="w-4 h-4" /> Update &amp; Restart
              </button>
            )}

            {/* Log output */}
            {(updating || reconnecting || updateLog.length > 0) && (
              <div className="bg-background border border-border rounded-lg p-3 font-mono text-xs max-h-72 overflow-y-auto space-y-0.5">
                {updateLog.map((line, i) => (
                  <div key={i} className={
                    line.type === "step"        ? "text-primary font-semibold mt-1" :
                    line.type === "error"       ? "text-red-400" :
                    line.type === "restarting"  ? "text-yellow-400" :
                    line.type === "info"        ? "text-muted-foreground italic" :
                    "text-foreground/70"
                  }>
                    {line.type === "step" ? `▶ ${line.message}` : `  ${line.message}`}
                  </div>
                ))}
                {reconnecting && (
                  <div className="text-yellow-400 animate-pulse mt-1">  ⟳ Waiting for service to come back up…</div>
                )}
              </div>
            )}

            {updateError && !reconnecting && (
              <div className="flex items-center gap-2 text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
                <XCircle className="w-3.5 h-3.5 shrink-0" /> {updateError}
              </div>
            )}

            {updateDone && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-xs text-green-400">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Update complete!
                </div>
                <button
                  onClick={() => {
                    localStorage.removeItem("heimdall_token");
                    window.location.href = "/login";
                  }}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/80 transition-colors"
                >
                  <RotateCcw className="w-3 h-3" /> Re-login
                </button>
              </div>
            )}
          </div>

          {/* Install info */}
          {sysInfo?.install_dir && (
            <p className="text-xs text-muted-foreground font-mono">Install dir: {sysInfo.install_dir}</p>
          )}
        </div>
      )}

      {/* ── Add Channel Modal ─────────────────────────────────────────────────── */}
      {showAddChannelModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-2xl p-6 w-full max-w-md space-y-4 max-h-[90vh] overflow-y-auto">
            <h2 className="text-base font-semibold">Add Channel</h2>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Type</label>
              <select
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                value={addChannelForm.type}
                onChange={e => setAddChannelForm((f: AddChannelForm) => ({ ...f, type: e.target.value as ChannelType, credentials: {} }))}>
                <option value="telegram">Telegram</option>
                <option value="discord">Discord</option>
                <option value="email">Email</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Name</label>
              <input
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="e.g. Heimdall Alerts"
                value={addChannelForm.name}
                onChange={e => setAddChannelForm(f => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">
                Targets <span className="text-muted-foreground/60">(comma-separated)</span>
              </label>
              <textarea
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary resize-none"
                rows={2}
                placeholder="e.g. 123456789, 987654321"
                value={addChannelForm.targets}
                onChange={e => setAddChannelForm(f => ({ ...f, targets: e.target.value }))}
              />
            </div>
            {CHANNEL_CREDENTIAL_FIELDS[addChannelForm.type].map(({ key, label, secret }) => (
              <div key={key} className="space-y-2">
                <label className="text-xs text-muted-foreground">{label}</label>
                <input
                  type={secret ? "password" : "text"}
                  className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                  placeholder={label}
                  value={addChannelForm.credentials[key] ?? ""}
                  onChange={e => setAddChannelForm(f => ({
                    ...f,
                    credentials: { ...f.credentials, [key]: e.target.value },
                  }))}
                />
              </div>
            ))}
            <div className="flex gap-2 pt-2">
              <button onClick={() => setShowAddChannelModal(false)}
                className="flex-1 text-sm border border-border rounded-lg py-2 text-muted-foreground hover:text-foreground transition-colors">
                Cancel
              </button>
              <button onClick={submitAddChannel} disabled={addChannelSaving || !addChannelForm.name}
                className="flex-1 text-sm bg-primary/20 text-primary hover:bg-primary/30 rounded-lg py-2 disabled:opacity-40 transition-colors">
                {addChannelSaving ? "Saving…" : "Add Channel"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Add Webhook Modal ─────────────────────────────────────────────────── */}
      {showAddWebhookModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-2xl p-6 w-full max-w-md space-y-4 max-h-[90vh] overflow-y-auto">
            <h2 className="text-base font-semibold">Add Webhook</h2>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">URL</label>
              <input
                type="url"
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="https://example.com/webhook"
                value={addWebhookForm.url}
                onChange={e => setAddWebhookForm(f => ({ ...f, url: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Secret (optional)</label>
              <input
                type="password"
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="Webhook secret for HMAC signing"
                value={addWebhookForm.secret}
                onChange={e => setAddWebhookForm(f => ({ ...f, secret: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Events</label>
              <div className="space-y-1">
                {WEBHOOK_EVENTS.map(event => (
                  <label key={event} className="flex items-center gap-2 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      checked={addWebhookForm.events.includes(event)}
                      onChange={e => {
                        const events = e.target.checked
                          ? [...addWebhookForm.events, event]
                          : addWebhookForm.events.filter(ev => ev !== event);
                        setAddWebhookForm(f => ({ ...f, events }));
                      }}
                    />
                    <span className="font-mono">{event}</span>
                  </label>
                ))}
              </div>
            </div>
            <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={addWebhookForm.enabled}
                onChange={e => setAddWebhookForm(f => ({ ...f, enabled: e.target.checked }))}
              />
              Enabled
            </label>
            <div className="flex gap-2 pt-2">
              <button onClick={() => setShowAddWebhookModal(false)}
                className="flex-1 text-sm border border-border rounded-lg py-2 text-muted-foreground hover:text-foreground transition-colors">
                Cancel
              </button>
              <button onClick={submitAddWebhook} disabled={savingWebhook || !addWebhookForm.url}
                className="flex-1 text-sm bg-primary/20 text-primary hover:bg-primary/30 rounded-lg py-2 disabled:opacity-40 transition-colors">
                {savingWebhook ? "Saving…" : "Add Webhook"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
