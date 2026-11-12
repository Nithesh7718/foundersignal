"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Building,
  CheckCircle2,
  LogOut,
  Menu,
  RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";

interface HeaderProps {
  onOpenMobileMenu?: () => void;
}

export function Header({ onOpenMobileMenu }: HeaderProps) {
  const { user, workspaces, activeWorkspace, setActiveWorkspace, logout } = useAuth();
  const [apiStatus, setApiStatus] = useState<"checking" | "connected" | "disconnected">("checking");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, 5000);

    async function checkHealth() {
      try {
        const res = await fetch(`${apiUrl}/health/ready`, {
          method: "GET",
          signal: controller.signal,
        });

        if (!isMounted) return;

        if (res.ok) {
          const data = await res.json();
          if (data.status === "ready") {
            setApiStatus("connected");
            return;
          }
        }
        setApiStatus("disconnected");
      } catch {
        if (!isMounted) return;
        setApiStatus("disconnected");
      } finally {
        clearTimeout(timeoutId);
      }
    }

    checkHealth();

    return () => {
      isMounted = false;
      controller.abort();
      clearTimeout(timeoutId);
    };
  }, [apiUrl]);

  return (
    <header className="h-16 border-b bg-card px-4 sm:px-8 flex items-center justify-between">
      <div className="flex items-center gap-3">
        {onOpenMobileMenu && (
          <button
            onClick={onOpenMobileMenu}
            aria-label="Open navigation menu"
            className="p-2 -ml-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent md:hidden transition-colors"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <div>
          <h1 className="text-base sm:text-lg font-bold text-foreground tracking-tight">
            Founder Cockpit
          </h1>
          <p className="text-xs text-muted-foreground hidden sm:block">
            Real-time visibility over business commitments, decisions, and delivery evidence.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3 sm:gap-4">
        {/* Workspace Selector Indicator */}
        {user && activeWorkspace && (
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-muted/30 text-xs font-medium">
            <Building className="h-3.5 w-3.5 text-primary" />
            {workspaces.length > 1 ? (
              <select
                value={activeWorkspace.id}
                onChange={(e) => {
                  const ws = workspaces.find((w) => w.id === e.target.value);
                  if (ws) setActiveWorkspace(ws);
                }}
                className="bg-transparent border-none text-xs font-medium text-foreground focus:outline-none cursor-pointer"
              >
                {workspaces.map((ws) => (
                  <option key={ws.id} value={ws.id}>
                    {ws.name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="text-foreground">{activeWorkspace.name}</span>
            )}
          </div>
        )}

        {/* Backend Connectivity Status Indicator */}
        <div className="flex items-center gap-2">
          {apiStatus === "connected" && (
            <Badge variant="success" className="gap-1.5 py-1 px-2.5">
              <CheckCircle2 className="h-3 w-3 text-emerald-600" />
              <span className="hidden sm:inline">API Connected</span>
              <span className="sm:hidden">Online</span>
            </Badge>
          )}
          {apiStatus === "checking" && (
            <Badge variant="outline" className="gap-1.5 py-1 px-2.5 text-muted-foreground">
              <RefreshCw className="h-3 w-3 animate-spin" />
              <span className="hidden sm:inline">Checking API...</span>
            </Badge>
          )}
          {apiStatus === "disconnected" && (
            <Badge variant="warning" className="gap-1.5 py-1 px-2.5">
              <AlertCircle className="h-3 w-3 text-amber-600" />
              <span className="hidden sm:inline">API Standby</span>
              <span className="sm:hidden">Offline</span>
            </Badge>
          )}
        </div>

        <div className="h-8 w-px bg-border mx-0.5" />

        {/* User Account / Auth Actions */}
        {user ? (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-primary/10 text-primary border border-primary/20 flex items-center justify-center font-bold text-xs">
                {user.full_name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase()}
              </div>
              <div className="text-left hidden lg:block">
                <span className="text-xs font-semibold text-foreground block leading-tight">
                  {user.full_name}
                </span>
                <span className="text-[10px] text-muted-foreground block truncate max-w-[120px]">
                  {user.email}
                </span>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              title="Sign out"
              className="text-muted-foreground hover:text-foreground h-8 w-8 p-0"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/login">Sign In</Link>
            </Button>
            <Button size="sm" asChild>
              <Link href="/register">Sign Up</Link>
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
