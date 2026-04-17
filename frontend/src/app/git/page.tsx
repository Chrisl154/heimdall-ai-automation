"use client";
import { useEffect, useState } from "react";
import { api, GitCommit, GitStatus } from "@/lib/api";
import { GitBranch, GitCommit as CommitIcon, CheckCircle2, AlertCircle } from "lucide-react";

export default function GitPage() {
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [commits, setCommits] = useState<GitCommit[]>([]);

  useEffect(() => {
    api.git.status().then(setStatus).catch(() => {});
    api.git.commits(15).then(setCommits).catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <h1 className="text-lg font-semibold">Git</h1>
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
  );
}
