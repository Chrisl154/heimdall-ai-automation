"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Lock, Unlock, Save, Plus, Trash2 } from "lucide-react";

type Tab = "providers" | "vault" | "channels";

const PROVIDER_KEYS = [
  { key: "anthropic_key", label: "Anthropic (Claude)", provider: "anthropic" },
  { key: "openai_key",    label: "OpenAI / Codex",     provider: "openai" },
  { key: "github_token",  label: "GitHub PAT",          provider: "github" },
];

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("providers");
  const [vaultKeys, setVaultKeys] = useState<string[]>([]);
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});

  const refreshKeys = () => api.vault.keys().then(r => setVaultKeys(r.keys)).catch(() => {});

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

  const TABS: { id: Tab; label: string }[] = [
    { id: "providers", label: "AI Providers" },
    { id: "vault",     label: "Vault" },
    { id: "channels",  label: "Channels" },
  ];

  return (
    <div className="p-6 overflow-y-auto h-full space-y-4">
      <h1 className="text-lg font-semibold">Settings</h1>
      <div className="flex gap-1 bg-secondary rounded-lg p-1 w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-1.5 rounded-md text-sm transition-colors ${tab === t.id ? "bg-card text-foreground shadow" : "text-muted-foreground hover:text-foreground"}`}>
            {t.label}
          </button>
        ))}
      </div>

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

      {tab === "channels" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Configure Telegram, Discord, or Email channels. Credentials are stored in the vault.
            This panel is implemented by Qwen task <code className="bg-secondary px-1 rounded text-xs">qwen-007</code>.
          </p>
          <div className="bg-card rounded-xl border border-border p-6 text-center text-muted-foreground text-sm">
            Coming soon — assigned to Qwen (task qwen-007)
          </div>
        </div>
      )}
    </div>
  );
}
