"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Columns3, Settings, GitBranch, MessageSquare, ScrollText, FolderSearch, BarChart2, CalendarClock, Cpu } from "lucide-react";

const nav = [
  { href: "/", label: "Chat", icon: MessageSquare },
  { href: "/tasks", label: "Kanban", icon: Columns3 },
  { href: "/workspace", label: "Workspace", icon: FolderSearch },
  { href: "/logs", label: "Logs", icon: ScrollText },
  { href: "/analytics", label: "Analytics", icon: BarChart2 },
  { href: "/schedule", label: "Schedules", icon: CalendarClock },
  { href: "/models", label: "Models", icon: Cpu },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/git", label: "Git", icon: GitBranch },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 flex flex-col bg-card border-r border-border py-4 gap-1 shrink-0">
      <div className="px-4 mb-4 flex items-center gap-2">
        <Bot className="w-6 h-6 text-primary" />
        <span className="font-bold text-lg tracking-tight">Heimdall</span>
      </div>
      {nav.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || (href !== "/" && pathname?.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-3 px-4 py-2.5 rounded-md mx-2 text-sm font-medium transition-colors
              ${active ? "bg-primary/20 text-primary" : "text-muted-foreground hover:bg-secondary hover:text-foreground"}`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        );
      })}
    </aside>
  );
}
