"use client";
import { useEffect, useState, useCallback } from "react";
import { api, GHRepo, GHStatus, GitCommit, GitStatus } from "@/lib/api";
import {
  GitBranch, GitCommit as CommitIcon, CheckCircle2, AlertCircle,
  Github, KeyRound, Loader2, Search, Star, Lock, Globe,
  FolderDown, RefreshCw, ChevronLeft, ChevronRight, LogOut,
  FolderOpen, ExternalLink, CheckCheck,
} from "lucide-react";

type Tab = "github" | "local";
type Sort = "updated" | "name" | "stars";

const LANG_COLORS: Record<string, string> = {
  TypeScript: "bg-blue-400/20 text-blue-400",
  JavaScript: "bg-yellow-400/20 text-yellow-400",
  Python:     "bg-green-400/20 text-green-400",
  Go:         "bg-cyan-400/20 text-cyan-400",
  Rust:       "bg-orange-400/20 text-orange-400",
  Java:       "bg-red-400/20 text-red-400",
  "C++":      "bg-purple-400/20 text-purple-400",
  C:          "bg-gray-400/20 text-gray-400",
  Shell:      "bg-emerald-400/20 text-emerald-400",
};

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d === 0) return "today";
  if (d === 1) return "yesterday";
  if (d < 30) return `${d}d ago`;
  const m = Math.floor(d / 30);
  if (m < 12) return `${m}mo ago`;
  return `${Math.floor(m / 12)}y ago`;
}

export default function GitPage() {
  const [tab, setTab] = useState<Tab>("github");

  // ── GitHub state ─────────────────────────────────────────────────────────────
  const [ghStatus, setGhStatus]     = useState<GHStatus | null>(null);
  const [repos, setRepos]           = useState<GHRepo[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [page, setPage]             = useState(1);
  const [hasMore, setHasMore]       = useState(true);
  const [sort, setSort]             = useState<Sort>("updated");
  const [search, setSearch]         = useState("");
  const [draftToken, setDraftToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connectErr, setConnectErr] = useState("");
  const [cloning, setCloning]       = useState<string | null>(null);
  const [cloneOk, setCloneOk]       = useState<Record<string, string>>({});

  // ── Local git state ───────────────────────────────────────────────────────────
  const [status, setStatus]   = useState<GitStatus | null>(null);
  const [commits, setCommits] = useState<GitCommit[]>([]);

  // ── Load GitHub status on mount ───────────────────────────────────────────────
  useEffect(() => {
    api.github.status().then(setGhStatus).catch(() => {});
  }, []);

  const loadRepos = useCallback(async (p: number, s: Sort) => {
    setReposLoading(true);
    try {
      const data = await api.github.repos(p, 30, s);
      setRepos(data);
      setHasMore(data.length === 30);
    } catch { /* ignore */ }
    setReposLoading(false);
  }, []);

  useEffect(() => {
    if (ghStatus?.connected) loadRepos(page, sort);
  }, [ghStatus?.connected, page, sort, loadRepos]);

  // ── Load local git on tab switch ──────────────────────────────────────────────
  useEffect(() => {
    if (tab === "local") {
      api.git.status().then(setStatus).catch(() => {});
      api.git.commits(20).then(setCommits).catch(() => {});
    }
  }, [tab]);

  // ── Connect ───────────────────────────────────────────────────────────────────
  const connectGitHub = async () => {
    const token = draftToken.trim();
    if (!token) return;
    setConnecting(true);
    setConnectErr("");
    try {
      const res = await api.github.connect(token);
      if (res.valid) {
        setDraftToken("");
        const st = await api.github.status();
        setGhStatus(st);
      } else {
        setConnectErr(res.error ?? "Invalid token");
      }
    } catch (e: unknown) {
      setConnectErr(e instanceof Error ? e.message : "Connection failed");
    }
    setConnecting(false);
  };

  // ── Disconnect ────────────────────────────────────────────────────────────────
  const disconnect = async () => {
    await api.github.disconnect();
    setGhStatus({ connected: false });
    setRepos([]);
  };

  // ── Clone ─────────────────────────────────────────────────────────────────────
  const cloneRepo = async (repo: GHRepo) => {
    setCloning(repo.full_name);
    try {
      const res = await api.github.clone(repo.full_name, repo.clone_url, true);
      setCloneOk(p => ({ ...p, [repo.full_name]: res.local_path }));
      const st = await api.github.status();
      setGhStatus(st);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Clone failed");
    }
    setCloning(null);
  };

  const filtered = repos.filter(r =>
    !search || r.name.toLowerCase().includes(search.toLowerCase()) ||
    r.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex items-center gap-1 px-6 pt-4 pb-0 border-b border-border">
        {(["github", "local"] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px
              ${tab === t ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
          >
            {t === "github" ? <Github className="w-3.5 h-3.5" /> : <GitBranch className="w-3.5 h-3.5" />}
            {t === "github" ? "GitHub" : "Local Git"}
          </button>
        ))}
      </div>

      {/* ── GITHUB TAB ─────────────────────────────────────────────────────────── */}
      {tab === "github" && (
        <div className="flex-1 overflow-y-auto p-6 space-y-5">

          {/* Not connected */}
          {!ghStatus?.connected && (
            <div className="max-w-lg mx-auto mt-8">
              <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                    <Github className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <h2 className="font-semibold">Connect GitHub</h2>
                    <p className="text-xs text-muted-foreground">Browse and clone your repositories</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">
                    Create a Personal Access Token with <code className="bg-secondary px-1 py-0.5 rounded text-[11px]">repo</code> scope at{" "}
                    <a href="https://github.com/settings/tokens/new" target="_blank" rel="noopener noreferrer"
                      className="text-primary hover:underline inline-flex items-center gap-0.5">
                      github.com/settings/tokens <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  </p>
                  <input
                    type="password"
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                    value={draftToken}
                    onChange={e => setDraftToken(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && connectGitHub()}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  {connectErr && <p className="text-xs text-red-400">{connectErr}</p>}
                  <button
                    onClick={connectGitHub}
                    disabled={!draftToken.trim() || connecting}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/80 disabled:opacity-50 transition-colors"
                  >
                    {connecting ? <><Loader2 className="w-4 h-4 animate-spin" /> Connecting…</> : <><KeyRound className="w-4 h-4" /> Connect GitHub</>}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Connected */}
          {ghStatus?.connected && (
            <>
              {/* Account header */}
              <div className="flex items-center gap-3 bg-card border border-border rounded-xl px-4 py-3">
                {ghStatus.avatar_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={ghStatus.avatar_url} alt={ghStatus.username} className="w-8 h-8 rounded-full" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{ghStatus.name || ghStatus.username}</p>
                  <p className="text-xs text-muted-foreground font-mono">@{ghStatus.username}</p>
                </div>
                {ghStatus.active_project && (
                  <div className="flex items-center gap-1.5 text-xs text-green-400 bg-green-400/10 border border-green-400/20 rounded-lg px-2.5 py-1.5">
                    <FolderOpen className="w-3.5 h-3.5" />
                    <span className="font-mono truncate max-w-48">{ghStatus.active_project.split(/[/\\]/).pop()}</span>
                    <span className="text-muted-foreground">active</span>
                  </div>
                )}
                <button onClick={disconnect} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-red-400 transition-colors">
                  <LogOut className="w-3.5 h-3.5" /> Disconnect
                </button>
              </div>

              {/* Search + sort */}
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                  <input
                    className="w-full bg-card border border-border rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                    placeholder="Filter repositories…"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                  />
                </div>
                <select
                  value={sort}
                  onChange={e => { setSort(e.target.value as Sort); setPage(1); }}
                  className="bg-card border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="updated">Recently updated</option>
                  <option value="name">Name</option>
                  <option value="stars">Stars</option>
                </select>
                <button
                  onClick={() => loadRepos(page, sort)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-secondary border border-border rounded-lg text-sm hover:bg-secondary/70 transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${reposLoading ? "animate-spin" : ""}`} />
                </button>
              </div>

              {/* Repo grid */}
              {reposLoading && repos.length === 0 ? (
                <div className="flex items-center justify-center py-16 text-muted-foreground">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading repositories…
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {filtered.map(repo => {
                    const isCloning = cloning === repo.full_name;
                    const clonedPath = cloneOk[repo.full_name];
                    const isActive = ghStatus.active_project?.endsWith(repo.name);
                    const langColor = repo.language ? (LANG_COLORS[repo.language] ?? "bg-secondary text-muted-foreground") : "";

                    return (
                      <div
                        key={repo.full_name}
                        className={`bg-card border rounded-xl p-4 flex flex-col gap-3 transition-colors
                          ${isActive ? "border-primary/40 bg-primary/5" : "border-border hover:border-border/80"}`}
                      >
                        {/* Repo header */}
                        <div className="flex items-start gap-2 min-w-0">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-medium truncate">{repo.name}</span>
                              {repo.private
                                ? <span className="flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 bg-secondary border border-border rounded text-muted-foreground"><Lock className="w-2.5 h-2.5" /> private</span>
                                : <span className="flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 bg-secondary border border-border rounded text-muted-foreground"><Globe className="w-2.5 h-2.5" /> public</span>
                              }
                              {isActive && <span className="text-[10px] px-1.5 py-0.5 bg-primary/10 border border-primary/30 rounded text-primary">active</span>}
                            </div>
                            {repo.description && (
                              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{repo.description}</p>
                            )}
                          </div>
                        </div>

                        {/* Meta */}
                        <div className="flex items-center gap-2 flex-wrap">
                          {repo.language && (
                            <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${langColor}`}>{repo.language}</span>
                          )}
                          {repo.stars > 0 && (
                            <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
                              <Star className="w-3 h-3" /> {repo.stars}
                            </span>
                          )}
                          <span className="text-xs text-muted-foreground ml-auto">{timeAgo(repo.updated_at)}</span>
                        </div>

                        {/* Clone button */}
                        {clonedPath ? (
                          <div className="flex items-center gap-2 text-xs text-green-400">
                            <CheckCheck className="w-3.5 h-3.5 shrink-0" />
                            <span className="font-mono truncate">{clonedPath}</span>
                          </div>
                        ) : (
                          <button
                            onClick={() => cloneRepo(repo)}
                            disabled={!!cloning}
                            className="flex items-center justify-center gap-1.5 w-full px-3 py-2 text-xs bg-primary text-primary-foreground rounded-lg hover:bg-primary/80 disabled:opacity-50 transition-colors"
                          >
                            {isCloning
                              ? <><Loader2 className="w-3 h-3 animate-spin" /> Cloning…</>
                              : isActive
                              ? <><RefreshCw className="w-3 h-3" /> Pull latest</>
                              : <><FolderDown className="w-3 h-3" /> Clone &amp; use</>
                            }
                          </button>
                        )}
                      </div>
                    );
                  })}

                  {filtered.length === 0 && !reposLoading && (
                    <div className="col-span-2 text-center py-12 text-muted-foreground text-sm">
                      {search ? `No repos matching "${search}"` : "No repositories found"}
                    </div>
                  )}
                </div>
              )}

              {/* Pagination */}
              {!search && (
                <div className="flex items-center justify-center gap-3 pt-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1 || reposLoading}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-secondary border border-border rounded-lg disabled:opacity-40 hover:bg-secondary/70 transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" /> Prev
                  </button>
                  <span className="text-sm text-muted-foreground">Page {page}</span>
                  <button
                    onClick={() => setPage(p => p + 1)}
                    disabled={!hasMore || reposLoading}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-secondary border border-border rounded-lg disabled:opacity-40 hover:bg-secondary/70 transition-colors"
                  >
                    Next <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── LOCAL GIT TAB ──────────────────────────────────────────────────────── */}
      {tab === "local" && (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {status && (
            <div className="bg-card rounded-xl border border-border p-4 flex items-center gap-6">
              <div className="flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-primary" />
                <span className="font-mono text-sm">{status.branch}</span>
              </div>
              <div className="flex items-center gap-1.5">
                {status.clean
                  ? <><CheckCircle2 className="w-4 h-4 text-green-400" /><span className="text-sm text-green-400">Clean</span></>
                  : <><AlertCircle className="w-4 h-4 text-yellow-400" /><span className="text-sm text-yellow-400">Dirty ({status.staged.length + status.unstaged.length} changes)</span></>
                }
              </div>
              {status.staged.length > 0 && (
                <div className="text-xs text-muted-foreground">{status.staged.length} staged</div>
              )}
            </div>
          )}

          <div>
            <h2 className="text-sm font-medium text-muted-foreground mb-3">Recent Commits</h2>
            <div className="space-y-2">
              {commits.map(c => (
                <div key={c.sha} className="bg-card rounded-lg border border-border p-3 flex gap-3 items-start">
                  <CommitIcon className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm truncate">{c.message}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      <span className="font-mono text-primary">{c.sha}</span> · {c.author} · {new Date(c.date).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
              {commits.length === 0 && <p className="text-sm text-muted-foreground">No commits found.</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
