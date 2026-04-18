"use client";

import { useState, useEffect } from "react";
import { Bot } from "lucide-react";

export default function LoginPage() {
    const [token, setToken] = useState("");
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const stored = localStorage.getItem("heimdall_token");
        if (stored) {
            window.location.href = "/";
            return;
        }
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get("error") === "1") {
            setError("Invalid token");
        }
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!token.trim()) {
            setError("Please enter a token");
            return;
        }
        localStorage.setItem("heimdall_token", token.trim());
        window.location.href = "/";
    };

    return (
        <div className="min-h-screen bg-background flex items-center justify-center">
            <div className="bg-card border border-border rounded-2xl p-8 w-full max-w-md">
                <div className="flex flex-col items-center mb-6">
                    <Bot className="w-16 h-16 text-primary mb-4" />
                    <h1 className="text-2xl font-bold text-foreground">Heimdall</h1>
                    <p className="text-muted-foreground mt-1">Enter your API token</p>
                </div>

                {error && (
                    <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm text-center">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm text-muted-foreground mb-1">Token</label>
                        <input
                            type="password"
                            value={token}
                            onChange={(e) => { setToken(e.target.value); setError(null); }}
                            className="w-full px-4 py-2 bg-input border border-border rounded-lg outline-none focus:border-primary"
                            placeholder="Enter your API token"
                            autoFocus
                        />
                    </div>

                    <button
                        type="submit"
                        className="w-full py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
                    >
                        Sign in
                    </button>
                </form>
            </div>
        </div>
    );
}
