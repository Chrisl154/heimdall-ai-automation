"use client";
import { useEffect, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";

const PUBLIC_PATHS = ["/login", "/setup"];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isPublic = PUBLIC_PATHS.some(p => pathname === p || pathname.startsWith(p + "/"));

  useEffect(() => {
    if (isPublic) return;

    fetch("/api/setup/status")
      .then(r => r.json())
      .then((s: { configured: boolean }) => {
        if (!s.configured) {
          window.location.href = "/setup";
          return;
        }
        const token = typeof window !== "undefined"
          ? localStorage.getItem("heimdall_token") ?? ""
          : "";
        if (!token) {
          window.location.href = "/login";
        }
      })
      .catch(() => {});
  }, [pathname, isPublic]);

  if (isPublic) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        {children}
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-hidden flex flex-col">{children}</main>
    </div>
  );
}
