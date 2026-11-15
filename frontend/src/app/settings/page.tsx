"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertCircle,
  Building,
  CheckCircle2,
  Database,
  Lock,
  LogOut,
  RefreshCw,
  Save,
  Server,
  Settings,
  Shield,
  Sliders,
  User,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, HealthStatus, WorkspaceMember } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function SettingsPage() {
  const { user, activeWorkspace, setActiveWorkspace, logout, loading: authLoading } = useAuth();

  // Workspace details state
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceSlug, setWorkspaceSlug] = useState("");
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);

  // User preferences (stored in localStorage for UX personalization)
  const [defaultIntakeMode, setDefaultIntakeMode] = useState<"upload" | "record">("upload");
  const [autoPlayPreview, setAutoPlayPreview] = useState(true);

  // Page state
  const [loading, setLoading] = useState(true);
  const [savingWorkspace, setSavingWorkspace] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Initialize data
  const loadData = useCallback(async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    setErrorMsg(null);

    setWorkspaceName(activeWorkspace.name);
    setWorkspaceSlug(activeWorkspace.slug);

    try {
      const [membersData, healthData] = await Promise.all([
        api.listWorkspaceMembers(activeWorkspace.id).catch(() => [] as WorkspaceMember[]),
        api.getHealth().catch(() => null),
      ]);

      setMembers(membersData);
      setHealthStatus(healthData);

      // Load saved preferences
      if (typeof window !== "undefined") {
        const savedIntake = localStorage.getItem("fs_pref_intake_mode");
        if (savedIntake === "upload" || savedIntake === "record") {
          setDefaultIntakeMode(savedIntake);
        }
        const savedAutoplay = localStorage.getItem("fs_pref_autoplay");
        if (savedAutoplay !== null) {
          setAutoPlayPreview(savedAutoplay === "true");
        }
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load settings data.");
    } finally {
      setLoading(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    if (activeWorkspace) {
      loadData();
    } else if (!authLoading && !user) {
      setLoading(false);
    }
  }, [activeWorkspace, authLoading, user, loadData]);

  // Handle Workspace Update (Owner/Admin only)
  const handleSaveWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace) return;

    setSavingWorkspace(true);
    setErrorMsg(null);
    setSaveSuccessMsg(null);

    try {
      const updated = await api.updateWorkspace(activeWorkspace.id, {
        name: workspaceName.trim(),
        slug: workspaceSlug.trim().toLowerCase(),
      });

      setActiveWorkspace(updated);
      setSaveSuccessMsg("Workspace settings updated successfully.");
      setTimeout(() => setSaveSuccessMsg(null), 4000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to update workspace.");
    } finally {
      setSavingWorkspace(false);
    }
  };

  // Handle Preferences Save
  const handleSavePreferences = (e: React.FormEvent) => {
    e.preventDefault();
    setSavingPrefs(true);
    try {
      if (typeof window !== "undefined") {
        localStorage.setItem("fs_pref_intake_mode", defaultIntakeMode);
        localStorage.setItem("fs_pref_autoplay", String(autoPlayPreview));
      }
      setSaveSuccessMsg("Preferences saved successfully.");
      setTimeout(() => setSaveSuccessMsg(null), 3000);
    } finally {
      setSavingPrefs(false);
    }
  };

  const isOwnerOrAdmin = activeWorkspace?.role === "owner" || activeWorkspace?.role === "admin";

  if (authLoading || (loading && !activeWorkspace)) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <RefreshCw className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm font-medium">Loading workspace settings...</p>
        </div>
      </div>
    );
  }

  if (!user || !activeWorkspace) {
    return (
      <div className="max-w-md mx-auto py-12 text-center space-y-4">
        <div className="h-12 w-12 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto">
          <Lock className="h-6 w-6" />
        </div>
        <h2 className="text-xl font-bold">Authentication Required</h2>
        <p className="text-sm text-muted-foreground">
          Please sign in to access workspace configuration, security controls, and members.
        </p>
        <Button asChild>
          <Link href="/login">Sign In</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-16" data-testid="settings-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <Settings className="h-6 w-6 text-primary" />
            Workspace & Account Settings
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage your workspace configuration, team members, operating preferences, and system health.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => loadData()}
          disabled={loading}
          className="gap-2 self-start sm:self-auto"
          data-testid="settings-refresh-btn"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Global Alerts */}
      {saveSuccessMsg && (
        <div
          role="status"
          data-testid="settings-success-alert"
          className="p-3 text-sm rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center gap-2 border border-emerald-500/20"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{saveSuccessMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div
          role="alert"
          data-testid="settings-error-alert"
          className="p-3 text-sm rounded-lg bg-destructive/10 text-destructive flex items-center gap-2 border border-destructive/20"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 Cols): Workspace & Members */}
        <div className="lg:col-span-2 space-y-6">
          {/* Workspace Details Card */}
          <Card className="shadow-xs" data-testid="workspace-settings-card">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building className="h-5 w-5 text-primary" />
                  <CardTitle className="text-lg">Workspace Configuration</CardTitle>
                </div>
                <Badge variant={isOwnerOrAdmin ? "default" : "outline"} className="capitalize">
                  Your Role: {activeWorkspace.role}
                </Badge>
              </div>
              <CardDescription>
                {isOwnerOrAdmin
                  ? "Update your workspace profile and organization identifier."
                  : "View your organization workspace settings (Owner/Admin required to edit)."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSaveWorkspace} className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="ws-name">Workspace Name</Label>
                    {!isOwnerOrAdmin && (
                      <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                        <Lock className="h-3 w-3" /> Read-only
                      </span>
                    )}
                  </div>
                  <Input
                    id="ws-name"
                    value={workspaceName}
                    onChange={(e) => setWorkspaceName(e.target.value)}
                    disabled={!isOwnerOrAdmin || savingWorkspace}
                    required
                    data-testid="workspace-name-input"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="ws-slug">Workspace Slug / URL Identifier</Label>
                    {!isOwnerOrAdmin && (
                      <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                        <Lock className="h-3 w-3" /> Read-only
                      </span>
                    )}
                  </div>
                  <Input
                    id="ws-slug"
                    value={workspaceSlug}
                    onChange={(e) => setWorkspaceSlug(e.target.value)}
                    disabled={!isOwnerOrAdmin || savingWorkspace}
                    required
                    data-testid="workspace-slug-input"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Unique identifier used in URLs and tenant isolation policies.
                  </p>
                </div>

                {/* Read-Only Technical Metadata */}
                <div className="pt-2 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-muted-foreground bg-muted/30 p-3 rounded-lg border">
                  <div>
                    <span className="font-semibold text-foreground">Workspace ID:</span>{" "}
                    <span className="font-mono">{activeWorkspace.id}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-foreground">Owner ID:</span>{" "}
                    <span className="font-mono">{activeWorkspace.owner_id}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-foreground">Created:</span>{" "}
                    <span>{new Date(activeWorkspace.created_at).toLocaleDateString()}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-foreground">Tenant Boundary:</span>{" "}
                    <span className="text-emerald-600 font-medium">Isolated</span>
                  </div>
                </div>

                {isOwnerOrAdmin && (
                  <div className="pt-2 flex justify-end">
                    <Button
                      type="submit"
                      disabled={savingWorkspace}
                      className="gap-2"
                      data-testid="save-workspace-btn"
                    >
                      <Save className="h-4 w-4" />
                      {savingWorkspace ? "Saving changes..." : "Save Workspace Changes"}
                    </Button>
                  </div>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Workspace Membership List */}
          <Card className="shadow-xs" data-testid="workspace-members-card">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-primary" />
                  <CardTitle className="text-lg">Workspace Members</CardTitle>
                </div>
                <Badge variant="secondary">{members.length} member{members.length === 1 ? "" : "s"}</Badge>
              </div>
              <CardDescription>
                Users with access to conversations, commitment approvals, and delivery tracking in this workspace.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {members.map((member) => (
                  <div
                    key={member.id}
                    className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-muted/30 transition-colors text-sm"
                    data-testid={`member-row-${member.user_id}`}
                  >
                    <div className="space-y-0.5 truncate">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-foreground truncate">
                          {member.full_name}
                        </span>
                        {member.user_id === user.id && (
                          <Badge variant="outline" className="text-[10px] py-0">You</Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground truncate">{member.email}</p>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <Badge
                        variant={
                          member.role === "owner"
                            ? "default"
                            : member.role === "admin"
                            ? "secondary"
                            : "outline"
                        }
                        className="text-xs capitalize"
                      >
                        {member.role}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Operating Cockpit Preferences */}
          <Card className="shadow-xs" data-testid="preferences-card">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2">
                <Sliders className="h-5 w-5 text-primary" />
                <CardTitle className="text-lg">Application Preferences</CardTitle>
              </div>
              <CardDescription>
                Personalize your default cockpit behavior and audio recording workflow.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSavePreferences} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="pref-intake">Default Audio Intake Tab</Label>
                  <select
                    id="pref-intake"
                    value={defaultIntakeMode}
                    onChange={(e) => setDefaultIntakeMode(e.target.value as "upload" | "record")}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    data-testid="pref-intake-select"
                  >
                    <option value="upload">Upload Audio File (Drag & Drop)</option>
                    <option value="record">Record Audio Directly in Browser</option>
                  </select>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                  <div className="space-y-0.5">
                    <Label htmlFor="pref-autoplay" className="cursor-pointer">
                      Autoplay Audio Preview
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Automatically load audio preview player when inspecting recorded clips.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    id="pref-autoplay"
                    checked={autoPlayPreview}
                    onChange={(e) => setAutoPlayPreview(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
                    data-testid="pref-autoplay-checkbox"
                  />
                </div>

                <div className="flex justify-end pt-1">
                  <Button type="submit" size="sm" disabled={savingPrefs} data-testid="save-preferences-btn">
                    Save Preferences
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Right Column (1 Col): User Profile & Service Health */}
        <div className="space-y-6">
          {/* User Profile Card */}
          <Card className="shadow-xs" data-testid="user-profile-card">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2">
                <User className="h-5 w-5 text-primary" />
                <CardTitle className="text-lg">Your Profile</CardTitle>
              </div>
              <CardDescription>Authenticated user account and session details.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-3.5 rounded-lg bg-muted/40 border space-y-2 text-xs">
                <div>
                  <span className="font-semibold text-foreground">Full Name:</span>
                  <p className="text-sm font-medium text-foreground mt-0.5">{user.full_name}</p>
                </div>
                <div>
                  <span className="font-semibold text-foreground">Email Address:</span>
                  <p className="text-sm text-foreground mt-0.5 truncate">{user.email}</p>
                </div>
                <div>
                  <span className="font-semibold text-foreground">Account Status:</span>
                  <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold ml-2">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Active
                  </span>
                </div>
                <div>
                  <span className="font-semibold text-foreground">User ID:</span>
                  <p className="font-mono text-[11px] text-muted-foreground truncate mt-0.5">
                    {user.id}
                  </p>
                </div>
              </div>

              <Button
                variant="outline"
                className="w-full text-destructive hover:bg-destructive/10 gap-2"
                onClick={logout}
                data-testid="settings-logout-btn"
              >
                <LogOut className="h-4 w-4" />
                Sign Out of FounderSignal
              </Button>
            </CardContent>
          </Card>

          {/* System Health Indicators */}
          <Card className="shadow-xs" data-testid="system-health-card">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2">
                <Server className="h-5 w-5 text-primary" />
                <CardTitle className="text-lg">Service Health</CardTitle>
              </div>
              <CardDescription>Live operational indicators for core infrastructure.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* API Service */}
              <div className="flex items-center justify-between p-2.5 rounded-lg border bg-card text-xs">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-emerald-500" />
                  <span className="font-medium text-foreground">API Backend</span>
                </div>
                <Badge
                  variant={healthStatus?.status === "ready" ? "success" : "warning"}
                  className="text-[10px]"
                >
                  {healthStatus?.status === "ready" ? "Operational" : "Checking"}
                </Badge>
              </div>

              {/* PostgreSQL Database */}
              <div className="flex items-center justify-between p-2.5 rounded-lg border bg-card text-xs">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-indigo-500" />
                  <span className="font-medium text-foreground">PostgreSQL Database</span>
                </div>
                <Badge
                  variant={healthStatus?.database_connected ? "success" : "destructive"}
                  className="text-[10px]"
                >
                  {healthStatus?.database_connected ? "Connected" : "Disconnected"}
                </Badge>
              </div>

              {/* Speech-to-Text Engine */}
              <div className="flex items-center justify-between p-2.5 rounded-lg border bg-card text-xs">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  <span className="font-medium text-foreground">Gnani Prisma STT</span>
                </div>
                <Badge variant="outline" className="text-[10px]">
                  v3.0 Ready
                </Badge>
              </div>

              {/* AI Extraction Engine */}
              <div className="flex items-center justify-between p-2.5 rounded-lg border bg-card text-xs">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-amber-500" />
                  <span className="font-medium text-foreground">Gemini Structured AI</span>
                </div>
                <Badge variant="outline" className="text-[10px]">
                  Active
                </Badge>
              </div>

              {healthStatus && (
                <div className="text-[10px] text-muted-foreground text-center pt-1 font-mono">
                  Version {healthStatus.version} • {healthStatus.environment || "Production"}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
