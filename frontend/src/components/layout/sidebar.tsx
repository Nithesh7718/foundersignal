"use client";

import React from "react";
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
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  active?: boolean;
  badge?: string;
}

const navItems: NavItem[] = [
  { name: "Dashboard", href: "#", icon: LayoutDashboard, active: true },
  { name: "Conversations & Audio", href: "#", icon: Mic },
  { name: "Extracted Commitments", href: "#", icon: FileText },
  { name: "Founder Approvals", href: "#", icon: ShieldCheck, badge: "0" },
  { name: "Evidence Graph", href: "#", icon: Network },
  { name: "Projects & Delivery", href: "#", icon: FolderKanban },
  { name: "Settings", href: "#", icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="w-64 border-r bg-card flex flex-col justify-between shrink-0 min-h-screen">
      <div>
        {/* Brand Header */}
        <div className="h-16 flex items-center px-6 border-b gap-3">
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
        </div>

        {/* Navigation Items */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <a
                key={item.name}
                href={item.href}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  item.active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className="h-4 w-4 shrink-0" />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <Badge variant="secondary" className="text-[10px] h-5 px-1.5 font-semibold">
                    {item.badge}
                  </Badge>
                )}
              </a>
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
            Phase 1: Foundation
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed flex items-center gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
          Evidence-first operating companion initialized.
        </p>
      </div>
    </aside>
  );
}
