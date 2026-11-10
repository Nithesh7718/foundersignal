import React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Activity,
  CheckCircle,
  FileCheck2,
  FolderGit2,
  Mic,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

export default function DashboardPlaceholder() {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Welcome & Vision Banner */}
      <div className="rounded-2xl border bg-gradient-to-r from-card to-muted/30 p-8 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="text-xs font-semibold py-1 px-2.5">
            Phase 1: Foundation
          </Badge>
          <Badge variant="success" className="text-xs font-semibold py-1 px-2.5">
            Monorepo Architecture Ready
          </Badge>
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Welcome to FounderSignal
          </h2>
          <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
            Your AI operating companion connects business conversations, decisions, commitments,
            people, projects, and delivery evidence into a single source of truth for founders.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-background border px-3 py-1.5 rounded-lg">
            <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
            Evidence over assumptions
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-background border px-3 py-1.5 rounded-lg">
            <ShieldAlert className="h-3.5 w-3.5 text-amber-500" />
            Human approval before action
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-background border px-3 py-1.5 rounded-lg">
            <FileCheck2 className="h-3.5 w-3.5 text-blue-500" />
            Source-attributed commitments
          </div>
        </div>
      </div>

      {/* Placeholder Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Conversations Tracked
            </CardTitle>
            <Mic className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground mt-1">
              Gnani Prisma STT ready for audio intake
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Extracted Commitments
            </CardTitle>
            <FileCheck2 className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground mt-1">
              Awaiting first conversation intake
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Pending Approvals
            </CardTitle>
            <ShieldAlert className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground mt-1">
              Human-in-the-loop gate active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Evidence Graph
            </CardTitle>
            <Activity className="h-4 w-4 text-indigo-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">Ready</div>
            <p className="text-xs text-muted-foreground mt-1">
              PostgreSQL schema initialized
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Roadmap & Next Phase Card */}
      <Card className="border-dashed">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">Foundational Architecture Verification</CardTitle>
          </div>
          <CardDescription>
            Phase 1 is complete. The application shell and underlying infrastructure are operational.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="p-4 rounded-lg bg-muted/50 border space-y-1">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <FolderGit2 className="h-4 w-4 text-primary" />
                Backend Service
              </span>
              <p className="text-xs text-muted-foreground">
                FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, Ruff, and Pytest initialized.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50 border space-y-1">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <CheckCircle className="h-4 w-4 text-emerald-500" />
                Database Engine
              </span>
              <p className="text-xs text-muted-foreground">
                PostgreSQL 16 running via Docker Compose with verified connection & migrations.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50 border space-y-1">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Activity className="h-4 w-4 text-indigo-500" />
                Frontend Shell
              </span>
              <p className="text-xs text-muted-foreground">
                Next.js App Router, strict TypeScript, Tailwind CSS, and shadcn/ui components.
              </p>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button variant="outline" size="sm" className="gap-2">
              <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
              Phase 1 Baseline Ready
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
