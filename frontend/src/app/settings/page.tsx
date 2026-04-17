"use client";
import { useEffect, useState } from "react";
import { api, MessagingChannel } from "@/lib/api";
import { Lock, Unlock, Save, Plus, Trash2, ToggleLeft, ToggleRight } from "lucide-react";

type Tab = "providers" | "vault" | "channels" | "restrictions";
type ChannelType = "telegram" | "discord" | "email";

const PROVIDER_KEYS = [
  { key: "anthropic_key", label: "Anthropic (Claude)", provider: "anthropic" },
  { key: "openai_key",    label: "OpenAI / Codex",     provider: "openai" },
  { key: "github_token",  label: "GitHub PAT",          provider: "github" },
];

const CHANNEL_CREDENTIAL_FIELDS: Record<ChannelType, { key: string; label: string; secret?: boolean }[]> = {
  telegram: [
    { key: "bot_token", label: "Bot Token", secret: true },
  ],
  discord: [
    { key: "bot_token", label: "Bot Token", secret: true },
  ],
  email: [
    { key: "smtp_host",     label: "SMTP Host" },
    { key: "smtp_port",     label: "SMTP Port" },
    { key: "smtp_user",     label: "SMTP User" },
    { key: "smtp_password", label: "SMTP Password", secret: true },
    { key: "imap_host",     label: "IMAP Host" },
    { key: "imap_port",     label: "IMAP Port" },
    { key: "imap_user",     label: "IMAP User" },
    { key: "imap_password", label: "IMAP Password", secret: true },
    { key: "from_address",          label: "From Address" },
    { key: "command_subject_prefix", label: "Command Subject Prefix" },
  ],
};

const TYPE_LABELS: Record<ChannelType, string> = {
  telegram: "Telegram",
  discord: "Discord",
  email: "Email",
};

interface AddChannelForm {
  type: ChannelType;
  name: string;
  targets: string;
  credentials: Record<string, string>;
}

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("providers");

  // ── Providers / Vault state ──────────────────────────────────────────────────
  const [vaultKeys, setVaultKeys] = useState<string[]>([]);
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});

  const refreshKeys = () =>
    api.vault.keys().then(r => setVaultKeys(r.keys)).catch(() => {});

  useEffect(() => { refreshKeys(); }, []);

  const saveKey = async (key: string) => {
    const val = keyInputs[key];
    if (!val) return;
    setSaving(s => ({ ...s, [key]: true }));
    await api.vault.set(key, val).catch(() => {});
    setKeyInputs(s => ({ ...s, [key]: "" }));
    await refreshKeys();
    setSaving(s => ({ ...s, [key]: false }));
  };

  const deleteKey = async (key: string) => {
    await api.vault.delete(key).catch(() => {});
    await refreshKeys();
  };

  // ── Restrictions state ───────────────────────────────────────────────────────
  const [restrictionsText, setRestrictionsText] = useState("");
  const [restrictionsDirty, setRestrictionsDirty] = useState(false);
  const [savingRestrictions, setSavingRestrictions] = useState(false);
  const [restrictionsError, setRestrictionsError] = useState("");

  useEffect(() => {
    if (tab === "restrictions" && !restrictionsText) {
      api.restrictions.get().then(data => {
        // API returns parsed object; convert back to YAML-like display via JSON for now
        setRestrictionsText(
          typeof data === "string" ? data : JSON.stringify(data, null, 2)
        );
      }).catch(() => {});
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
  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm] = useState<AddChannelForm>({
    type: "telegram",
    name: "",
    targets: "",
    credentials: {},
  });
  const [addSaving, setAddSaving] = useState(false);

  const refreshChannels = async () => {
    setChannelsLoading(true);
    try {
      const list = await api.messaging.channels();
      setChannels(list);
    } catch {}
    setChannelsLoading(false);
  };

  useEffect(() => {
    if (tab === "channels") refreshChannels();
  }, [tab]);

  const toggleChannel = async (ch: MessagingChannel) => {
    await api.messaging.updateChannel(ch.id, { enabled: !ch.enabled }).catch(() => {});
    await refreshChannels();
  };

  const deleteChannel = async (id: string) => {
    await api.messaging.deleteChannel(id).catch(() => {});
    await refreshChannels();
  };

  const openAddModal = () => {
    setAddForm({ type: "telegram", name: "", targets: "", credentials: {} });
    setShowAddModal(true);
  };

  const submitAddChannel = async () => {
    if (!addForm.name) return;
    setAddSaving(true);
    try {
      const targets = addForm.targets.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
      await api.messaging.addChannel({
        type: addForm.type,
        name: addForm.name,
        targets,
        credentials: addForm.credentials,
      });
      setShowAddModal(false);
      await refreshChannels();
    } catch {}
    setAddSaving(false);
  };

  const TABS: { id: Tab; label: string }[] = [
    { id: "providers",    label: "AI Providers" },
    { id: "vault",        label: "Vault" },
    { id: "channels",     label: "Channels" },
    { id: "restrictions", label: "Restrictions" },
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
            <button onClick={openAddModal}
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
                {ch.enabled
                  ? <ToggleRight className="w-5 h-5" />
                  : <ToggleLeft className="w-5 h-5" />}
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

      {/* ── Add Channel Modal ─────────────────────────────────────────────────── */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-2xl p-6 w-full max-w-md space-y-4 max-h-[90vh] overflow-y-auto">
            <h2 className="text-base font-semibold">Add Channel</h2>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Type</label>
              <select
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                value={addForm.type}
                onChange={e => setAddForm(f => ({ ...f, type: e.target.value as ChannelType, credentials: {} }))}>
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
                value={addForm.name}
                onChange={e => setAddForm(f => ({ ...f, name: e.target.value }))}
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">
                Targets <span className="text-muted-foreground/60">(chat IDs / channel IDs / email addresses, comma-separated)</span>
              </label>
              <textarea
                className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary resize-none"
                rows={2}
                placeholder="e.g. 123456789, 987654321"
                value={addForm.targets}
                onChange={e => setAddForm(f => ({ ...f, targets: e.target.value }))}
              />
            </div>

            {CHANNEL_CREDENTIAL_FIELDS[addForm.type].map(({ key, label, secret }) => (
              <div key={key} className="space-y-2">
                <label className="text-xs text-muted-foreground">{label}</label>
                <input
                  type={secret ? "password" : "text"}
                  className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
                  placeholder={label}
                  value={addForm.credentials[key] ?? ""}
                  onChange={e => setAddForm(f => ({
                    ...f,
                    credentials: { ...f.credentials, [key]: e.target.value },
                  }))}
                />
              </div>
            ))}

            <div className="flex gap-2 pt-2">
              <button onClick={() => setShowAddModal(false)}
                className="flex-1 text-sm border border-border rounded-lg py-2 text-muted-foreground hover:text-foreground transition-colors">
                Cancel
              </button>
              <button onClick={submitAddChannel} disabled={addSaving || !addForm.name}
                className="flex-1 text-sm bg-primary/20 text-primary hover:bg-primary/30 rounded-lg py-2 disabled:opacity-40 transition-colors">
                {addSaving ? "Saving…" : "Add Channel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
