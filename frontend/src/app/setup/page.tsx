"use client";

import { useState, useEffect } from "react";
import { Bot } from "lucide-react";

interface SetupStatus {
    configured: boolean;
    has_vault_key: boolean;
    has_api_token: boolean;
}

interface GenerateKeyResponse {
    key: string;
}

interface InitResponse {
    ok: boolean;
    message: string;
}

export default function SetupPage() {
    const [status, setStatus] = useState<SetupStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [step, setStep] = useState(0);
    const [vaultKey, setVaultKey] = useState("");
    const [apiToken, setApiToken] = useState("");
    const [anthropicKey, setAnthropicKey] = useState("");
    const [ollamaUrl, setOllamaUrl] = useState("http://127.0.0.1:11434");
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    useEffect(() => {
        fetch("/api/setup/status")
            .then((res) => res.json() as Promise<SetupStatus>)
            .then((s) => {
                setStatus(s);
                if (s.configured) {
                    window.location.href = "/";
                    return;
                }
                setLoading(false);
            })
            .catch((err) => {
                setError(err.message || "Failed to load setup status");
                setLoading(false);
            });
    }, []);

    const generateVaultKey = async () => {
        try {
            const res = await fetch("/api/setup/generate-key");
            const data = await res.json() as GenerateKeyResponse;
            setVaultKey(data.key);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Failed to generate key";
            setError(msg);
        }
    };

    const generateApiToken = () => {
        const bytes = new Uint8Array(16);
        window.crypto.getRandomValues(bytes);
        const token = Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
        setApiToken(token);
    };

    const copyToClipboard = async (text: string) => {
        try {
            await navigator.clipboard.writeText(text);
            alert("Copied to clipboard!");
        } catch {
            alert("Failed to copy");
        }
    };

    const handleNext = () => {
        setError(null);
        if (step < 2) setStep(step + 1);
    };

    const handleBack = () => {
        setError(null);
        if (step > 0) setStep(step - 1);
    };

    const handleFinish = async () => {
        setError(null);
        setSuccess(null);
        try {
            const res = await fetch("/api/setup/init", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    vault_key: vaultKey,
                    api_token: apiToken,
                    anthropic_key: anthropicKey,
                    ollama_url: ollamaUrl,
                }),
            });
            const data = await res.json() as InitResponse;
            if (data.ok) {
                setSuccess("Setup complete — restart Heimdall, then sign in. Run: heimdall restart");
            } else {
                setError(data.message || "Setup failed");
            }
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Setup failed";
            setError(msg);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="text-muted-foreground">Loading...</div>
            </div>
        );
    }

    if (error && step === 2 && !success) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="bg-card border border-border rounded-2xl p-8 w-full max-w-md">
                    <Bot className="w-16 h-16 text-red-400 mb-4" />
                    <h1 className="text-2xl font-bold text-foreground mb-2">Setup Failed</h1>
                    <p className="text-muted-foreground">{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background">
            <div className="container mx-auto px-4 py-8">
                <div className="max-w-2xl mx-auto">
                    <div className="text-center mb-8">
                        <Bot className="w-16 h-16 text-primary mx-auto mb-4" />
                        <h1 className="text-3xl font-bold text-foreground">Heimdall Setup</h1>
                        <p className="text-muted-foreground mt-2">Configure your Heimdall instance</p>
                    </div>

                    {/* Step indicators */}
                    <div className="flex justify-center gap-2 mb-8">
                        {[0, 1, 2].map((i) => (
                            <div
                                key={i}
                                className={`w-3 h-3 rounded-full transition-colors ${step === i ? "bg-primary" : step > i ? "bg-primary/50" : "bg-muted"
                                    }`}
                            />
                        ))}
                    </div>

                    {/* Step 1: Vault Key */}
                    {step === 0 && (
                        <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
                            <h2 className="text-xl font-semibold">Generate a vault key</h2>
                            <p className="text-muted-foreground text-sm">
                                This key encrypts all your stored secrets. Generate it now — you cannot change it later without losing vault data.
                            </p>

                            <div className="space-y-2">
                                <label className="text-sm text-muted-foreground">Vault Key</label>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={vaultKey}
                                        readOnly
                                        className="flex-1 px-4 py-2 bg-input border border-border rounded-lg font-mono text-sm outline-none focus:border-primary"
                                        placeholder="Click Generate Key to create a vault key"
                                    />
                                    <button
                                        onClick={generateVaultKey}
                                        className="px-4 py-2 bg-primary/20 text-primary hover:bg-primary/30 rounded-lg text-sm transition-colors"
                                    >
                                        Generate Key
                                    </button>
                                </div>
                                {vaultKey && (
                                    <button
                                        onClick={() => copyToClipboard(vaultKey)}
                                        className="text-xs text-primary hover:underline"
                                    >
                                        Copy to clipboard
                                    </button>
                                )}
                            </div>

                            <div className="flex justify-end pt-4">
                                <button
                                    onClick={handleNext}
                                    disabled={!vaultKey}
                                    className="px-6 py-2 bg-primary text-primary-foreground rounded-lg disabled:opacity-40 transition-colors"
                                >
                                    Next
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Step 2: API Token */}
                    {step === 1 && (
                        <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
                            <h2 className="text-xl font-semibold">Set an API token</h2>
                            <p className="text-muted-foreground text-sm">
                                This token protects your Heimdall API. Use a long random string.
                            </p>

                            <div className="space-y-2">
                                <label className="text-sm text-muted-foreground">API Token</label>
                                <div className="flex gap-2">
                                    <input
                                        type="password"
                                        value={apiToken}
                                        onChange={(e) => setApiToken(e.target.value)}
                                        className="flex-1 px-4 py-2 bg-input border border-border rounded-lg font-mono text-sm outline-none focus:border-primary"
                                        placeholder="Enter or generate a token"
                                    />
                                    <button
                                        onClick={generateApiToken}
                                        className="px-4 py-2 bg-primary/20 text-primary hover:bg-primary/30 rounded-lg text-sm transition-colors"
                                    >
                                        Generate
                                    </button>
                                </div>
                                {apiToken && (
                                    <button
                                        onClick={() => copyToClipboard(apiToken)}
                                        className="text-xs text-primary hover:underline"
                                    >
                                        Copy to clipboard
                                    </button>
                                )}
                            </div>

                            <div className="flex justify-between pt-4">
                                <button
                                    onClick={handleBack}
                                    className="px-6 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition-colors"
                                >
                                    Back
                                </button>
                                <button
                                    onClick={handleNext}
                                    disabled={!apiToken}
                                    className="px-6 py-2 bg-primary text-primary-foreground rounded-lg disabled:opacity-40 transition-colors"
                                >
                                    Next
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Step 3: Connections */}
                    {step === 2 && (
                        <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
                            <h2 className="text-xl font-semibold">Configure connections</h2>
                            <p className="text-muted-foreground text-sm">
                                Set up your LLM providers and other connections.
                            </p>

                            <div className="space-y-4">
                                <div>
                                    <label className="text-sm text-muted-foreground block mb-1">Anthropic API Key (optional)</label>
                                    <input
                                        type="password"
                                        value={anthropicKey}
                                        onChange={(e) => setAnthropicKey(e.target.value)}
                                        className="w-full px-4 py-2 bg-input border border-border rounded-lg font-mono text-sm outline-none focus:border-primary"
                                        placeholder="sk-ant-..."
                                    />
                                </div>

                                <div>
                                    <label className="text-sm text-muted-foreground block mb-1">Ollama URL</label>
                                    <input
                                        type="text"
                                        value={ollamaUrl}
                                        onChange={(e) => setOllamaUrl(e.target.value)}
                                        className="w-full px-4 py-2 bg-input border border-border rounded-lg font-mono text-sm outline-none focus:border-primary"
                                        placeholder="http://127.0.0.1:11434"
                                    />
                                </div>
                            </div>

                            {success && (
                                <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
                                    {success}
                                </div>
                            )}

                            {error && (
                                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                                    {error}
                                </div>
                            )}

                            <div className="flex justify-between pt-4">
                                <button
                                    onClick={handleBack}
                                    className="px-6 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition-colors"
                                >
                                    Back
                                </button>
                                <button
                                    onClick={handleFinish}
                                    disabled={!vaultKey || !apiToken}
                                    className="px-6 py-2 bg-primary text-primary-foreground rounded-lg disabled:opacity-40 transition-colors"
                                >
                                    Finish Setup
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
