"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  CheckCircle2,
  FileText,
  FolderKanban,
  LayoutDashboard,
  Mic,
  Network,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

interface SidebarProps {
  onClose?: () => void;
  className?: string;
}

export function SidebarContent({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const { user, activeWorkspace } = useAuth();
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);

  useEffect(() => {
    let isMounted = true;
    async function fetchPendingCount() {
      if (!user || !activeWorkspace) {
        if (isMounted) setPendingApprovalsCount(0);
        return;
      }
      try {
        const inferred = await api.listWorkspaceCommitments(activeWorkspace.id, "inferred");
        if (isMounted) {
          setPendingApprovalsCount(inferred.length);
        }
      } catch {
        // Fallback silently if offline or unauthenticated
      }
    }

    fetchPendingCount();
    return () => {
      isMounted = false;
    };
  }, [user, activeWorkspace]);

  const navItems: NavItem[] = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Conversations & Audio", href: "/conversations", icon: Mic },
    { name: "Extracted Commitments", href: "/#approvals-section", icon: FileText },
    {
      name: "Founder Approvals",
      href: "/#approvals-section",
      icon: ShieldCheck,
      badge: String(pendingApprovalsCount),
    },
    { name: "Evidence Graph", href: "/evidence", icon: Network },
    { name: "Projects & Delivery", href: "/projects", icon: FolderKanban },
    { name: "Settings", href: "/settings", icon: Settings },
  ];

  return (
    <div className="flex flex-col justify-between h-full">
      <div>
        {/* Brand Header */}
        <div className="h-16 flex items-center justify-between px-6 border-b">
          <Link href="/" className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center font-bold shadow-sm">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <span className="font-bold text-base tracking-tight text-foreground block leading-tight">
                FounderSignal
              </span>
              <span className="text-[11px] text-muted-foreground font-medium block">
                AI Operating Companion
              </span>
            </div>
          </Link>
          {onClose && (
            <button
              onClick={onClose}
              aria-label="Close navigation menu"
              className="p-1 rounded-md text-muted-foreground hover:text-foreground md:hidden"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Navigation Items */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : item.href !== "#" && pathname.startsWith(item.href);

            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={onClose}
                data-testid={`nav-${item.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary font-semibold"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className="h-4 w-4 shrink-0" />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <Badge
                    variant={item.badge !== "0" ? "secondary" : "secondary"}
                    className={`text-[10px] h-5 px-1.5 font-semibold ${
                      item.badge !== "0"
                        ? "bg-amber-500/15 text-amber-700 dark:text-amber-300 font-bold border-amber-500/30"
                        : ""
                    }`}
                  >
                    {item.badge}
                  </Badge>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* System Status Footer */}
      <div className="p-4 border-t m-3 rounded-xl bg-muted/40 space-y-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-xs font-semibold text-foreground">
            Phase 2A: Voice-to-Commitment
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed flex items-center gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
          Evidence-backed audio intake & tenant isolation ready.
        </p>
      </div>
    </div>
  );
}

export function Sidebar({ className = "" }: SidebarProps) {
  return (
    <aside className={`w-64 border-r bg-card shrink-0 min-h-screen ${className}`}>
      <SidebarContent />
    </aside>
  );
}
