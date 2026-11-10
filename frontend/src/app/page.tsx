import React from "react";
import Link from "next/link";
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
  ArrowRight,
  CheckCircle,
  FileCheck2,
  FolderGit2,
  Mic,
  Plus,
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
            Phase 2A: Voice-to-Commitment Foundation
          </Badge>
          <Badge variant="success" className="text-xs font-semibold py-1 px-2.5">
            Authentication & Audio Intake Active
          </Badge>
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            FounderSignal Operating Cockpit
          </h2>
          <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
            Connect business conversations, decisions, commitments, people, and delivery evidence into a single source of truth for founders.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <Button asChild className="gap-2">
            <Link href="/conversations/new">
              <Plus className="h-4 w-4" />
              Upload Audio Update
            </Link>
          </Button>
          <Button variant="outline" asChild className="gap-2">
            <Link href="/conversations">
              View Conversations
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Conversations Tracked
            </CardTitle>
            <Mic className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">Intake Active</div>
            <p className="text-xs text-muted-foreground mt-1">
              Gnani Prisma STT & LocalStorageAdapter ready
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
            <div className="text-2xl font-bold">Evidence Ready</div>
            <p className="text-xs text-muted-foreground mt-1">
              UUID models & schema migrations applied
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Tenant Isolation
            </CardTitle>
            <ShieldAlert className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">Strict</div>
            <p className="text-xs text-muted-foreground mt-1">
              Workspaces & token revocation enforced
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Database Foundation
            </CardTitle>
            <Activity className="h-4 w-4 text-indigo-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">PostgreSQL 16</div>
            <p className="text-xs text-muted-foreground mt-1">
              Alembic verified, zero drift
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Roadmap & Next Phase Card */}
      <Card className="border-dashed">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">Phase 2A Foundation Verified</CardTitle>
          </div>
          <CardDescription>
            Secure audio intake, multi-tenant workspace isolation, and core data models are operational.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="p-4 rounded-lg bg-muted/50 border space-y-1">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <FolderGit2 className="h-4 w-4 text-primary" />
                Auth & Workspaces
              </span>
              <p className="text-xs text-muted-foreground">
                JWT auth, bcrypt hashing, token revocation, and strict cross-tenant isolation.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50 border space-y-1">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <CheckCircle className="h-4 w-4 text-emerald-500" />
                Audio Intake Storage
              </span>
              <p className="text-xs text-muted-foreground">
                Magic-bytes audio validation, 25MB limit enforcement, and traversal protection.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50 border space-y-1">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Activity className="h-4 w-4 text-indigo-500" />
                STT Provider Ready
              </span>
              <p className="text-xs text-muted-foreground">
                Official Gnani Prisma STT contract with mock safeguards for development.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
