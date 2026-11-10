"use client";

import React, { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, Bell, CheckCircle2, Menu, RefreshCw } from "lucide-react";

interface HeaderProps {
  onOpenMobileMenu?: () => void;
}

export function Header({ onOpenMobileMenu }: HeaderProps) {
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
        {/* Backend Connectivity Status Indicator */}
        <div className="flex items-center gap-2">
          {apiStatus === "connected" && (
            <Badge variant="success" className="gap-1.5 py-1 px-2.5">
              <CheckCircle2 className="h-3 w-3 text-emerald-600" />
              <span className="hidden xs:inline">API Connected</span>
              <span className="xs:hidden">Online</span>
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
              <span className="hidden xs:inline">API Standby</span>
              <span className="xs:hidden">Offline</span>
            </Badge>
          )}
        </div>

        <button
          aria-label="Notifications"
          className="h-9 w-9 rounded-lg border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        >
          <Bell className="h-4 w-4" />
        </button>

        <div className="h-8 w-px bg-border mx-0.5 sm:mx-1" />

        <div className="flex items-center gap-2.5 pl-1">
          <div className="h-8 w-8 rounded-full bg-primary/10 text-primary border border-primary/20 flex items-center justify-center font-bold text-xs">
            FS
          </div>
          <div className="text-left hidden md:block">
            <span className="text-xs font-semibold text-foreground block leading-tight">
              Founder Mode
            </span>
            <span className="text-[10px] text-muted-foreground block">
              Workspace Admin
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
