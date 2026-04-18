"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { ScheduledTask, CreateScheduleBody } from "@/lib/api";
import { CalendarClock } from "lucide-react";

export default function SchedulePage() {
  const [schedules, setSchedules] = useState<ScheduledTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.schedules
      .list()
      .then(setSchedules)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async (body: CreateScheduleBody) => {
    try {
      const created = await api.schedules.create(body);
      setSchedules((prev: ScheduledTask[]) => [...prev, created]);
      setShowModal(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    }
  };

  const handleToggle = async (id: string, current: boolean) => {
    try {
      const updated = await api.schedules.update(id, { enabled: !current });
      setSchedules((prev: ScheduledTask[]) =>
        prev.map((s: ScheduledTask) => (s.id === id ? updated : s))
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.schedules.delete(id);
      setSchedules((prev: ScheduledTask[]) =>
        prev.filter((s: ScheduledTask) => s.id !== id)
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
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

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-red-400">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-foreground">Schedules</h1>
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 flex items-center gap-2"
          >
            <CalendarClock className="w-4 h-4" />
            Add Schedule
          </button>
        </div>

        {schedules.length === 0 ? (
          <div className="text-center text-muted-foreground py-12">
            <CalendarClock className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No schedules configured.</p>
            <p className="mt-2">Click "Add Schedule" to create one.</p>
          </div>
        ) : (
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="w-full text-left">
              <thead className="bg-muted/50 border-b border-border">
                <tr>
                  <th className="px-4 py-3 text-sm font-medium text-muted-foreground">ID</th>
                  <th className="px-4 py-3 text-sm font-medium text-muted-foreground">Cron</th>
                  <th className="px-4 py-3 text-sm font-medium text-muted-foreground">Task Title</th>
                  <th className="px-4 py-3 text-sm font-medium text-muted-foreground">Priority</th>
                  <th className="px-4 py-3 text-sm font-medium text-muted-foreground">Enabled</th>
                  <th className="px-4 py-3 text-sm font-medium text-muted-foreground">Last Run</th>
                  <th className="px-4 py-3 text-sm font-medium text-muted-foreground">Next Run</th>
                  <th className="px-4 py-3 text-sm font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((schedule: ScheduledTask) => (
                  <tr
                    key={schedule.id}
                    className="border-b border-border/50 hover:bg-muted/25"
                  >
                    <td className="px-4 py-3 text-sm font-mono text-muted-foreground">
                      {schedule.id}
                    </td>
                    <td className="px-4 py-3 text-sm font-mono">{schedule.cron}</td>
                    <td className="px-4 py-3 text-sm">{schedule.task_template.title}</td>
                    <td className="px-4 py-3 text-sm">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          schedule.task_template.priority === "critical"
                            ? "bg-red-500/20 text-red-400"
                            : schedule.task_template.priority === "high"
                            ? "bg-orange-500/20 text-orange-400"
                            : schedule.task_template.priority === "medium"
                            ? "bg-yellow-500/20 text-yellow-400"
                            : "bg-green-500/20 text-green-400"
                        }`}
                      >
                        {schedule.task_template.priority}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <button
                        onClick={() => handleToggle(schedule.id, schedule.enabled)}
                        className={`px-3 py-1 rounded text-xs font-medium ${
                          schedule.enabled
                            ? "bg-green-500/20 text-green-400 hover:bg-green-500/30"
                            : "bg-gray-500/20 text-gray-400 hover:bg-gray-500/30"
                        }`}
                      >
                        {schedule.enabled ? "Enabled" : "Disabled"}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {schedule.last_run || "-"}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {schedule.next_run || "-"}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <button
                        onClick={() => handleDelete(schedule.id)}
                        className="px-3 py-1 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <Modal onClose={() => setShowModal(false)} onSubmit={handleCreate} />
      )}
    </div>
  );
}

function Modal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (body: CreateScheduleBody) => Promise<void>;
}) {
  const [cron, setCron] = useState("0 9 * * 1-5");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [tags, setTags] = useState("");
  const [maxIterations, setMaxIterations] = useState(3);
  const [outputPath, setOutputPath] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    try {
      await onSubmit({
        cron,
        title,
        description,
        priority,
        tags: tags.split(",").map((t: string) => t.trim()).filter(Boolean),
        depends_on: [],
        max_review_iterations: maxIterations,
        output_path: outputPath,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-card border border-border rounded-lg w-full max-w-lg p-6">
        <h2 className="text-xl font-bold text-foreground mb-4">Add Schedule</h2>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Cron Expression
            </label>
            <input
              type="text"
              value={cron}
              onChange={(e) => setCron(e.target.value)}
              placeholder="0 9 * * 1-5"
              className="w-full px-3 py-2 bg-background border border-border rounded text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <p className="text-xs text-muted-foreground mt-1">
              5-field cron: min hour day month weekday
            </p>
          </div>

          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Task Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 bg-background border border-border rounded text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 bg-background border border-border rounded text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Priority
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full px-3 py-2 bg-background border border-border rounded text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Tags (comma-separated)
            </label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="frontend, react, typescript"
              className="w-full px-3 py-2 bg-background border border-border rounded text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Max Review Iterations
            </label>
            <input
              type="number"
              value={maxIterations}
              onChange={(e) => setMaxIterations(Number(e.target.value))}
              min={1}
              max={10}
              className="w-full px-3 py-2 bg-background border border-border rounded text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm text-muted-foreground mb-1">
              Output Path
            </label>
            <input
              type="text"
              value={outputPath}
              onChange={(e) => setOutputPath(e.target.value)}
              placeholder="workspace/current/my-task"
              className="w-full px-3 py-2 bg-background border border-border rounded text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-muted text-foreground rounded hover:bg-muted/80"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90"
            >
              Add Schedule
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
