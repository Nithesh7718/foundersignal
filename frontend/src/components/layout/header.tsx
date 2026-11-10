"use client";

import React, { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Bell, CheckCircle2, RefreshCw, AlertCircle } from "lucide-react";

export function Header() {
  const [apiStatus, setApiStatus] = useState<"checking" | "connected" | "disconnected">("checking");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch(`${apiUrl}/health`, { method: "GET" });
        if (res.ok) {
          const data = await res.json();
          if (data.status === "healthy" || data.status === "degraded") {
            setApiStatus("connected");
            return;
          }
        }
        setApiStatus("disconnected");
      } catch {
        setApiStatus("disconnected");
      }
    }

    checkHealth();
  }, [apiUrl]);

  return (
    <header className="h-16 border-b bg-card px-8 flex items-center justify-between">
      <div>
        <h1 className="text-lg font-bold text-foreground tracking-tight">
          Founder Cockpit
        </h1>
        <p className="text-xs text-muted-foreground">
          Real-time visibility over business commitments, decisions, and delivery evidence.
        </p>
      </div>

      <div className="flex items-center gap-4">
        {/* Backend Connectivity Status Indicator */}
        <div className="flex items-center gap-2">
          {apiStatus === "connected" && (
            <Badge variant="success" className="gap-1.5 py-1 px-2.5">
              <CheckCircle2 className="h-3 w-3 text-emerald-600" />
              API Connected
            </Badge>
          )}
          {apiStatus === "checking" && (
            <Badge variant="outline" className="gap-1.5 py-1 px-2.5 text-muted-foreground">
              <RefreshCw className="h-3 w-3 animate-spin" />
              Checking API...
            </Badge>
          )}
          {apiStatus === "disconnected" && (
            <Badge variant="warning" className="gap-1.5 py-1 px-2.5">
              <AlertCircle className="h-3 w-3 text-amber-600" />
              API Standby
            </Badge>
          )}
        </div>

        <button
          aria-label="Notifications"
          className="h-9 w-9 rounded-lg border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        >
          <Bell className="h-4 w-4" />
        </button>

        <div className="h-8 w-px bg-border mx-1" />

        <div className="flex items-center gap-2.5 pl-1">
          <div className="h-8 w-8 rounded-full bg-primary/10 text-primary border border-primary/20 flex items-center justify-center font-bold text-xs">
            FS
          </div>
          <div className="text-left hidden sm:block">
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
