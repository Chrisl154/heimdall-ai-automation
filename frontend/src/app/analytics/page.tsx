"use client";
import { useEffect, useState } from "react";
import { api, AnalyticsData } from "@/lib/api";
import { BarChart2, TrendingUp, Activity, CheckCircle2 } from "lucide-react";

export default function AnalyticsPage() {
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.analytics()
            .then(setData)
            .catch(() => { })
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-muted-foreground">Loading analytics...</div>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-muted-foreground">No analytics data available</div>
            </div>
        );
    }

    const maxPriority = Math.max(
        data.tasks_by_priority.low,
        data.tasks_by_priority.medium,
        data.tasks_by_priority.high,
        data.tasks_by_priority.critical,
        1
    );

    const maxTag = Math.max(...Object.values(data.tasks_by_tag), 1);

    const priorityColors: { [key: string]: string } = {
        low: "bg-green-500",
        medium: "bg-yellow-500",
        high: "bg-orange-500",
        critical: "bg-red-500",
    };

    return (
        <div className="flex flex-col h-full bg-background">
            <div className="px-6 py-4 border-b border-border">
                <div className="flex items-center gap-2">
                    <BarChart2 className="w-5 h-5 text-primary" />
                    <h1 className="text-xl font-semibold">Analytics Dashboard</h1>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Summary Cards */}
                <div className="grid grid-cols-5 gap-4">
                    <div className="bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-muted-foreground mb-1">Total Tasks</div>
                        <div className="text-2xl font-semibold">{data.total_tasks}</div>
                    </div>
                    <div className="bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-muted-foreground mb-1">Completed</div>
                        <div className="text-2xl font-semibold text-green-400">{data.completed}</div>
                    </div>
                    <div className="bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-muted-foreground mb-1">Failed</div>
                        <div className="text-2xl font-semibold text-red-400">{data.failed}</div>
                    </div>
                    <div className="bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-muted-foreground mb-1">Escalated</div>
                        <div className="text-2xl font-semibold text-yellow-400">{data.escalated}</div>
                    </div>
                    <div className="bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-muted-foreground mb-1">Success Rate</div>
                        <div className="text-2xl font-semibold text-blue-400">{data.success_rate}%</div>
                    </div>
                </div>

                {/* Tasks by Priority Bar Chart */}
                <div className="bg-card border border-border rounded-xl p-4">
                    <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
                        <Activity className="w-4 h-4" /> Tasks by Priority
                    </h2>
                    <div className="space-y-3">
                        {Object.entries(data.tasks_by_priority).map(([priority, count]) => (
                            <div key={priority} className="space-y-1">
                                <div className="flex justify-between text-xs">
                                    <span className="text-muted-foreground capitalize">{priority}</span>
                                    <span className="text-foreground">{count}</span>
                                </div>
                                <div className="h-8 bg-secondary rounded-lg overflow-hidden">
                                    <div
                                        className={`h-full ${priorityColors[priority]} transition-all`}
                                        style={{ width: `${(count / maxPriority) * 100}%` }}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Tasks by Tag Bar Chart */}
                {Object.keys(data.tasks_by_tag).length > 0 && (
                    <div className="bg-card border border-border rounded-xl p-4">
                        <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
                            <TrendingUp className="w-4 h-4" /> Tasks by Tag
                        </h2>
                        <div className="space-y-2">
                            {Object.entries(data.tasks_by_tag).map(([tag, count]) => (
                                <div key={tag} className="space-y-1">
                                    <div className="flex justify-between text-xs">
                                        <span className="text-muted-foreground">{tag}</span>
                                        <span className="text-foreground">{count}</span>
                                    </div>
                                    <div className="h-6 bg-secondary rounded-lg overflow-hidden">
                                        <div
                                            className="h-full bg-primary/60 transition-all"
                                            style={{ width: `${(count / maxTag) * 100}%` }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Averages Row */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Avg Iterations to Completion
                        </div>
                        <div className="text-2xl font-semibold">{data.avg_iterations}</div>
                    </div>
                    <div className="bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                            <Activity className="w-3 h-3" /> Avg Duration (seconds)
                        </div>
                        <div className="text-2xl font-semibold">{data.avg_duration_seconds}</div>
                    </div>
                </div>

                {/* Recent Completions Table */}
                {data.recent_completions.length > 0 && (
                    <div className="bg-card border border-border rounded-xl p-4">
                        <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4" /> Recent Completions
                        </h2>
                        <div className="space-y-2">
                            {data.recent_completions.map((task) => (
                                <div
                                    key={task.id}
                                    className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg"
                                >
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm font-medium truncate">{task.title}</div>
                                        <div className="text-xs text-muted-foreground">{task.completed_at}</div>
                                    </div>
                                    <div className="text-xs text-muted-foreground ml-4">
                                        {task.iterations} iter
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
