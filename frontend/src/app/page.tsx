"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
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
import { Input } from "@/components/ui/input";
import {
  Activity,
  ArrowRight,
  CheckCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileAudio,
  FileCheck2,
  FolderGit2,
  Mic,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Volume2,
  X,
  Zap,
} from "lucide-react";
import { api, Commitment, Conversation } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { AudioRecorder } from "@/components/audio-recorder";

export default function FounderOperatingCockpit() {
  const { user, activeWorkspace, loading: authLoading } = useAuth();

  // Dynamic Workspace Data State
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Search and Filter States
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<
    "all" | "meeting" | "client_call" | "voice_note"
  >("all");
  const [commitmentStatusFilter, setCommitmentStatusFilter] = useState<
    "all" | "inferred" | "confirmed" | "in_progress" | "completed"
  >("all");

  // Inline Review Feedback State
  const [updatingCommitmentId, setUpdatingCommitmentId] = useState<string | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  // Quick In-Dashboard Audio Recording Modal State
  const [isQuickRecordOpen, setIsQuickRecordOpen] = useState(false);
  const [quickRecordTitle, setQuickRecordTitle] = useState("");
  const [quickRecordType, setQuickRecordType] = useState("voice_note");
  const [isUploadingQuickRecord, setIsUploadingQuickRecord] = useState(false);

  // Unauthenticated Interactive Demo Preview Tab
  const [previewTab, setPreviewTab] = useState<"intake" | "commitments" | "isolation">("intake");
  const [demoApproved, setDemoApproved] = useState(false);

  // Fetch Live Workspace Data
  const fetchData = useCallback(
    async (showRefreshIndicator = false) => {
      if (!activeWorkspace) return;
      if (showRefreshIndicator) {
        setIsRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      try {
        const [convList, commList] = await Promise.all([
          api.listConversations(activeWorkspace.id).catch(() => [] as Conversation[]),
          api.listWorkspaceCommitments(activeWorkspace.id).catch(() => [] as Commitment[]),
        ]);

        setConversations(convList);
        setCommitments(commList);
        setLastRefreshedAt(new Date());
      } catch (err: unknown) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to synchronize workspace signals.");
        }
      } finally {
        setLoading(false);
        setIsRefreshing(false);
      }
    },
    [activeWorkspace]
  );

  useEffect(() => {
    if (activeWorkspace) {
      fetchData();
    } else if (!authLoading && !user) {
      setLoading(false);
    }
  }, [activeWorkspace, authLoading, user, fetchData]);

  // Compute Live Metrics
  const metrics = useMemo(() => {
    const totalConversations = conversations.length;
    const meetingsCount = conversations.filter((c) => c.conversation_type === "meeting").length;
    const voiceNotesCount = conversations.filter((c) => c.conversation_type === "voice_note").length;
    const callsCount = conversations.filter((c) => c.conversation_type === "client_call").length;

    const totalCommitments = commitments.length;
    const inferredCount = commitments.filter((c) => c.status === "inferred").length;
    const confirmedCount = commitments.filter((c) => c.status === "confirmed").length;
    const inProgressCount = commitments.filter((c) => c.status === "in_progress").length;
    const completedCount = commitments.filter((c) => c.status === "completed").length;

    const totalAudioFiles = conversations.reduce(
      (acc, c) => acc + (c.audio_assets ? c.audio_assets.length : 0),
      0
    );

    return {
      totalConversations,
      meetingsCount,
      voiceNotesCount,
      callsCount,
      totalCommitments,
      inferredCount,
      confirmedCount,
      inProgressCount,
      completedCount,
      totalAudioFiles,
    };
  }, [conversations, commitments]);

  // Filtered Conversations
  const filteredConversations = useMemo(() => {
    return conversations.filter((conv) => {
      const matchesSearch =
        conv.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        conv.conversation_type.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType =
        selectedTypeFilter === "all" || conv.conversation_type === selectedTypeFilter;
      return matchesSearch && matchesType;
    });
  }, [conversations, searchQuery, selectedTypeFilter]);

  // Filtered Commitments
  const filteredCommitments = useMemo(() => {
    return commitments.filter((comm) => {
      const matchesStatus =
        commitmentStatusFilter === "all" || comm.status === commitmentStatusFilter;
      const matchesSearch =
        comm.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        comm.source_quote.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (comm.speaker && comm.speaker.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesStatus && matchesSearch;
    });
  }, [commitments, commitmentStatusFilter, searchQuery]);

  // Handle Dynamic Status Updates for Commitments
  const handleUpdateCommitmentStatus = async (commitmentId: string, newStatus: string) => {
    if (!activeWorkspace) return;
    setUpdatingCommitmentId(commitmentId);
    setActionSuccessMessage(null);

    // Save current state for rollback on API failure
    const previousCommitments = [...commitments];

    // Optimistically update local commitments array immediately
    setCommitments((prev) =>
      prev.map((c) => (c.id === commitmentId ? { ...c, status: newStatus } : c))
    );

    try {
      const updated = await api.updateCommitment(activeWorkspace.id, commitmentId, {
        status: newStatus,
      });

      // Synchronize with verified backend record
      setCommitments((prev) =>
        prev.map((c) => (c.id === commitmentId ? { ...c, status: updated.status } : c))
      );

      const statusLabels: Record<string, string> = {
        confirmed: "Approved commitment",
        in_progress: "Marked commitment in-progress",
        completed: "Completed commitment",
        rejected: "Dismissed commitment",
      };

      setActionSuccessMessage(statusLabels[newStatus] || `Updated status to ${newStatus}`);
      setTimeout(() => setActionSuccessMessage(null), 3000);
    } catch (err: unknown) {
      // Revert optimistic update immediately on failure
      setCommitments(previousCommitments);
      setError(err instanceof Error ? err.message : "Failed to update commitment.");
    } finally {
      setUpdatingCommitmentId(null);
    }
  };

  // Quick In-Dashboard Audio Recording Handler
  const handleQuickRecordingComplete = async (file: File) => {
    if (!activeWorkspace) return;
    setIsUploadingQuickRecord(true);
    setError(null);

    try {
      const title =
        quickRecordTitle.trim() ||
        `Quick Voice Note (${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })})`;

      const newConv = await api.createConversation(activeWorkspace.id, {
        title,
        conversation_type: quickRecordType,
      });

      await api.uploadAudio(activeWorkspace.id, newConv.id, file);

      // Refresh data
      await fetchData(true);
      setIsQuickRecordOpen(false);
      setQuickRecordTitle("");
      setActionSuccessMessage("Voice note recorded and uploaded successfully!");
      setTimeout(() => setActionSuccessMessage(null), 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to upload recorded voice note.");
    } finally {
      setIsUploadingQuickRecord(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-12">
      {/* Welcome & Vision Cockpit Banner */}
      <section
        aria-label="Operating Cockpit Header"
        className="rounded-2xl border bg-gradient-to-r from-card via-card to-primary/5 p-6 sm:p-8 shadow-sm space-y-5"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {/* Badges kept for test verification and live information */}
            <Badge variant="outline" className="text-xs font-semibold py-1 px-2.5">
              Phase 2A: Voice-to-Commitment Foundation
            </Badge>
            <Badge variant="success" className="text-xs font-semibold py-1 px-2.5">
              Authentication & Audio Intake Active
            </Badge>
            {activeWorkspace && (
              <Badge variant="secondary" className="text-xs font-medium py-1 px-2.5 flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Workspace: {activeWorkspace.name}
              </Badge>
            )}
          </div>

          {user && activeWorkspace && (
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => fetchData(true)}
                disabled={isRefreshing || loading}
                className="text-xs text-muted-foreground hover:text-foreground h-8 gap-1.5"
                title="Synchronize workspace signals"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin text-primary" : ""}`} />
                <span>
                  {isRefreshing
                    ? "Syncing..."
                    : lastRefreshedAt
                    ? `Synced ${lastRefreshedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
                    : "Sync Signals"}
                </span>
              </Button>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl flex items-center gap-2.5">
            <span>FounderSignal Operating Cockpit</span>
            {user && (
              <span className="text-base sm:text-lg font-normal text-muted-foreground">
                • Welcome back, {user.full_name.split(" ")[0]}
              </span>
            )}
          </h2>
          <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
            Connect business conversations, decisions, commitments, people, and delivery evidence into a single source of truth for founders.
          </p>
        </div>

        {/* Action Controls Bar */}
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <Button asChild className="gap-2 shadow-sm">
            <Link href="/conversations/new">
              <Plus className="h-4 w-4" />
              Upload Audio Update
            </Link>
          </Button>

          {user && activeWorkspace && (
            <Button
              variant="secondary"
              onClick={() => {
                setQuickRecordTitle(`Voice Note ${new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" })}`);
                setIsQuickRecordOpen(true);
              }}
              className="gap-2 border hover:border-primary/50"
            >
              <Mic className="h-4 w-4 text-primary animate-pulse" />
              Quick Voice Note
            </Button>
          )}

          <Button variant="outline" asChild className="gap-2">
            <Link href="/conversations">
              View Conversations
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>

        {/* Toast Notification for Action Confirmation */}
        {actionSuccessMessage && (
          <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 text-sm border border-emerald-200 dark:border-emerald-800 flex items-center gap-2 transition-all">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>{actionSuccessMessage}</span>
          </div>
        )}

        {error && (
          <div className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20 flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </section>

      {/* Quick Record Modal */}
      {isQuickRecordOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-card w-full max-w-lg rounded-2xl border shadow-xl p-6 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                  <Mic className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-semibold text-base">Quick Voice Capture</h3>
                  <p className="text-xs text-muted-foreground">Record instantly to your workspace</p>
                </div>
              </div>
              <button
                onClick={() => setIsQuickRecordOpen(false)}
                className="p-1 rounded-md text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-foreground">Note Title</label>
                <Input
                  value={quickRecordTitle}
                  onChange={(e) => setQuickRecordTitle(e.target.value)}
                  placeholder="e.g. Daily Standup or Founder Memo"
                  className="text-sm"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-foreground">Type</label>
                <select
                  value={quickRecordType}
                  onChange={(e) => setQuickRecordType(e.target.value)}
                  className="w-full text-xs rounded-md border bg-background px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="voice_note">Voice Note</option>
                  <option value="meeting">Team Meeting</option>
                  <option value="client_call">Client Call</option>
                  <option value="interview">Interview</option>
                </select>
              </div>

              <div className="pt-2">
                <AudioRecorder
                  onRecordingComplete={handleQuickRecordingComplete}
                  onRecordingDiscard={() => setIsQuickRecordOpen(false)}
                  disabled={isUploadingQuickRecord}
                />
              </div>

              {isUploadingQuickRecord && (
                <div className="flex items-center justify-center gap-2 text-xs text-primary font-medium py-2">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span>Creating conversation & uploading audio...</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Dynamic Overview KPI Cards */}
      <section aria-label="Operating Key Performance Indicators">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {/* Card 1: Tracked Conversations */}
          <Card className="hover:shadow-sm transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Conversations Tracked
              </CardTitle>
              <Mic className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold flex items-baseline gap-2">
                <span>{user && activeWorkspace ? metrics.totalConversations : "Intake Active"}</span>
                {user && activeWorkspace && (
                  <span className="text-xs font-normal text-muted-foreground">
                    recorded
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {user && activeWorkspace
                  ? `${metrics.meetingsCount} meetings • ${metrics.voiceNotesCount} voice notes`
                  : "Gnani Prisma STT & LocalStorageAdapter ready"}
              </p>
            </CardContent>
          </Card>

          {/* Card 2: Extracted Commitments */}
          <Card className="hover:shadow-sm transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Extracted Commitments
              </CardTitle>
              <FileCheck2 className="h-4 w-4 text-emerald-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold flex items-baseline gap-2">
                <span>{user && activeWorkspace ? metrics.totalCommitments : "Evidence Ready"}</span>
                {user && activeWorkspace && (
                  <span className="text-xs font-normal text-muted-foreground">
                    signals
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {user && activeWorkspace
                  ? `${metrics.confirmedCount} confirmed • ${metrics.completedCount} completed`
                  : "UUID models & schema migrations applied"}
              </p>
            </CardContent>
          </Card>

          {/* Card 3: Pending Approvals */}
          <Card
            className={`transition-shadow ${
              metrics.inferredCount > 0 ? "border-amber-500/50 bg-amber-500/[0.02]" : "hover:shadow-sm"
            }`}
          >
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Founder Approvals
              </CardTitle>
              <ShieldAlert
                className={`h-4 w-4 ${
                  metrics.inferredCount > 0 ? "text-amber-500 animate-pulse" : "text-emerald-500"
                }`}
              />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold flex items-baseline gap-2">
                {user && activeWorkspace ? (
                  <>
                    <span className={metrics.inferredCount > 0 ? "text-amber-600 dark:text-amber-400" : ""}>
                      {metrics.inferredCount}
                    </span>
                    <span className="text-xs font-normal text-muted-foreground">
                      awaiting review
                    </span>
                  </>
                ) : (
                  <span>Strict</span>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {user && activeWorkspace
                  ? metrics.inferredCount > 0
                    ? "Action needed: Verify inferred business promises"
                    : "Zero pending unreviewed items"
                  : "Workspaces & token revocation enforced"}
              </p>
            </CardContent>
          </Card>

          {/* Card 4: Audio Evidence Volume */}
          <Card className="hover:shadow-sm transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Database & Audio Assets
              </CardTitle>
              <Activity className="h-4 w-4 text-indigo-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold flex items-baseline gap-2">
                <span>{user && activeWorkspace ? `${metrics.totalAudioFiles} Files` : "PostgreSQL 16"}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {user && activeWorkspace
                  ? "Stored in isolated tenant partitions"
                  : "Alembic verified, zero drift"}
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Authenticated Dynamic Workspace Cockpit */}
      {user && activeWorkspace ? (
        <div className="space-y-8">
          {/* Dynamic Section 1: Pending Founder Approvals & Commitments Review */}
          <section
            id="approvals-section"
            aria-label="Commitment Approvals Cockpit"
            className="space-y-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                  <h3 className="text-lg font-bold tracking-tight text-foreground">
                    Founder Approvals & Commitments
                  </h3>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Every commitment links directly to verbatim transcript quotes. Confirm or reject inferred items to maintain clean evidence.
                </p>
              </div>

              {/* Status Filter Tabs */}
              <div className="flex flex-wrap items-center gap-1.5 bg-muted/60 p-1 rounded-lg text-xs">
                {(
                  [
                    { key: "all", label: `All (${commitments.length})` },
                    { key: "inferred", label: `Needs Review (${metrics.inferredCount})` },
                    { key: "confirmed", label: `Confirmed (${metrics.confirmedCount})` },
                    { key: "in_progress", label: `In Progress (${metrics.inProgressCount})` },
                    { key: "completed", label: `Done (${metrics.completedCount})` },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setCommitmentStatusFilter(tab.key)}
                    className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                      commitmentStatusFilter === tab.key
                        ? "bg-background text-foreground shadow-sm font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Commitments List with CSS Containment */}
            <div
              className="space-y-3"
              style={{
                contentVisibility: "auto",
                containIntrinsicSize: "auto 350px",
              }}
            >
              {filteredCommitments.length === 0 ? (
                <Card className="border-dashed py-8 text-center bg-card/50">
                  <CardContent className="space-y-2">
                    <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto" />
                    <p className="text-sm font-medium text-foreground">
                      {commitmentStatusFilter === "inferred"
                        ? "All caught up! Zero commitments require founder approval."
                        : "No commitments match your current filter."}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {commitmentStatusFilter === "inferred"
                        ? "Upload or record new conversations to extract upcoming commitments."
                        : "Try selecting 'All' or adjusting your search keyword."}
                    </p>
                  </CardContent>
                </Card>
              ) : (
                filteredCommitments.slice(0, 6).map((comm) => {
                  const isUpdating = updatingCommitmentId === comm.id;
                  const confidencePct = comm.confidence_score
                    ? Math.round(comm.confidence_score * 100)
                    : null;

                  return (
                    <Card
                      key={comm.id}
                      className="border transition-all hover:border-primary/40 shadow-sm"
                    >
                      <CardContent className="p-4 sm:p-5 space-y-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="space-y-1 max-w-2xl">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge
                                variant={
                                  comm.status === "confirmed"
                                    ? "success"
                                    : comm.status === "inferred"
                                    ? "warning"
                                    : comm.status === "completed"
                                    ? "secondary"
                                    : "outline"
                                }
                                className="text-[11px] capitalize font-medium"
                              >
                                {comm.status.replace("_", " ")}
                              </Badge>

                              {confidencePct !== null && (
                                <span
                                  className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                                    confidencePct >= 85
                                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                      : confidencePct >= 65
                                      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                                      : "bg-muted text-muted-foreground"
                                  }`}
                                >
                                  {confidencePct}% Confidence
                                </span>
                              )}

                              {comm.speaker && (
                                <span className="text-xs text-muted-foreground flex items-center gap-1">
                                  <span>Speaker:</span>
                                  <strong className="text-foreground">{comm.speaker}</strong>
                                </span>
                              )}
                            </div>

                            <h4 className="text-sm sm:text-base font-semibold text-foreground pt-0.5">
                              {comm.title}
                            </h4>
                          </div>

                          {/* Quick 1-Click Status Action Buttons */}
                          <div className="flex items-center gap-1.5 shrink-0">
                            {comm.status === "inferred" && (
                              <>
                                <Button
                                  size="sm"
                                  variant="default"
                                  disabled={isUpdating}
                                  onClick={() => handleUpdateCommitmentStatus(comm.id, "confirmed")}
                                  className="h-8 gap-1 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                                >
                                  <ThumbsUp className="h-3.5 w-3.5" />
                                  <span>Approve</span>
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={isUpdating}
                                  onClick={() => handleUpdateCommitmentStatus(comm.id, "rejected")}
                                  className="h-8 gap-1 text-xs text-destructive hover:bg-destructive/10"
                                >
                                  <ThumbsDown className="h-3.5 w-3.5" />
                                  <span>Dismiss</span>
                                </Button>
                              </>
                            )}

                            {comm.status === "confirmed" && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={isUpdating}
                                  onClick={() => handleUpdateCommitmentStatus(comm.id, "in_progress")}
                                  className="h-8 text-xs"
                                >
                                  Start Progress
                                </Button>
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  disabled={isUpdating}
                                  onClick={() => handleUpdateCommitmentStatus(comm.id, "completed")}
                                  className="h-8 text-xs gap-1"
                                >
                                  <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                                  <span>Mark Done</span>
                                </Button>
                              </>
                            )}

                            {comm.status === "in_progress" && (
                              <Button
                                size="sm"
                                variant="default"
                                disabled={isUpdating}
                                onClick={() => handleUpdateCommitmentStatus(comm.id, "completed")}
                                className="h-8 text-xs gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                              >
                                <CheckCircle className="h-3.5 w-3.5" />
                                <span>Complete</span>
                              </Button>
                            )}
                          </div>
                        </div>

                        {/* Evidence Source Quotation Box */}
                        {comm.source_quote && (
                          <div className="rounded-lg bg-muted/40 border p-2.5 text-xs text-muted-foreground flex items-start gap-2">
                            <span className="text-primary font-serif text-lg leading-none shrink-0">“</span>
                            <p className="italic text-foreground/90 leading-relaxed">
                              {comm.source_quote}
                            </p>
                          </div>
                        )}

                        <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                          <span className="flex items-center gap-1.5">
                            <Clock className="h-3 w-3" />
                            Created {new Date(comm.created_at).toLocaleDateString()}
                          </span>

                          <Link
                            href={`/conversations/${comm.conversation_id}`}
                            className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
                          >
                            <span>Inspect source conversation</span>
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </div>
          </section>

          {/* Dynamic Section 2: Recent Conversations & Audio Stream */}
          <section aria-label="Recent Conversations Feed" className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Mic className="h-5 w-5 text-primary" />
                  <h3 className="text-lg font-bold tracking-tight text-foreground">
                    Recent Conversations & Audio Evidence
                  </h3>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Real-time recording intake with Gnani Prisma STT and automated signal extraction.
                </p>
              </div>

              {/* Dynamic Filter Controls */}
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative w-48 sm:w-56">
                  <Search className="h-3.5 w-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by title..."
                    className="pl-8 h-8 text-xs"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-1 bg-muted/60 p-0.5 rounded-lg text-xs">
                  {(
                    [
                      { key: "all", label: "All" },
                      { key: "meeting", label: "Meetings" },
                      { key: "voice_note", label: "Notes" },
                      { key: "client_call", label: "Calls" },
                    ] as const
                  ).map((typeBtn) => (
                    <button
                      key={typeBtn.key}
                      onClick={() => setSelectedTypeFilter(typeBtn.key)}
                      className={`px-2.5 py-1 rounded-md transition-colors ${
                        selectedTypeFilter === typeBtn.key
                          ? "bg-background text-foreground shadow-sm font-semibold"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {typeBtn.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Conversation Grid with CSS Containment */}
            <div
              className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
              style={{
                contentVisibility: "auto",
                containIntrinsicSize: "auto 280px",
              }}
            >
              {filteredConversations.length === 0 ? (
                <div className="sm:col-span-2 lg:col-span-3">
                  <Card className="border-dashed py-10 text-center">
                    <CardHeader className="space-y-2">
                      <div className="mx-auto h-12 w-12 rounded-full bg-primary/10 text-primary flex items-center justify-center">
                        <Mic className="h-6 w-6" />
                      </div>
                      <CardTitle className="text-base">No matching conversations found</CardTitle>
                      <CardDescription className="max-w-sm mx-auto text-xs">
                        Record a voice note or upload a meeting recording to start tracking commitments.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="flex justify-center gap-2">
                      <Button asChild size="sm">
                        <Link href="/conversations/new">
                          <Plus className="h-4 w-4 mr-1.5" />
                          Record Audio
                        </Link>
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              ) : (
                filteredConversations.slice(0, 6).map((conv) => {
                  const hasAudio = conv.audio_assets && conv.audio_assets.length > 0;
                  const firstAsset = hasAudio ? conv.audio_assets[0] : null;

                  return (
                    <Link
                      key={conv.id}
                      href={`/conversations/${conv.id}`}
                      className="group focus:outline-none block"
                    >
                      <Card className="h-full group-hover:border-primary/60 group-hover:shadow-md transition-all flex flex-col justify-between">
                        <CardHeader className="pb-2.5 space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <Badge variant="outline" className="text-[10px] uppercase font-semibold">
                              {conv.conversation_type.replace("_", " ")}
                            </Badge>
                            <Badge
                              variant={conv.status === "uploaded" ? "success" : "secondary"}
                              className="capitalize text-[10px]"
                            >
                              {conv.status}
                            </Badge>
                          </div>
                          <CardTitle className="text-sm font-semibold group-hover:text-primary transition-colors line-clamp-2">
                            {conv.title}
                          </CardTitle>
                        </CardHeader>

                        <CardContent className="pt-0 space-y-3 text-xs text-muted-foreground">
                          <div className="flex flex-wrap items-center gap-2 pt-1 border-t">
                            {hasAudio && (
                              <span className="inline-flex items-center gap-1 text-[11px] text-foreground font-medium bg-muted/60 px-2 py-0.5 rounded">
                                <FileAudio className="h-3 w-3 text-primary" />
                                {firstAsset?.mime_type.includes("webm")
                                  ? "WebM Recording"
                                  : "WAV Audio"}
                              </span>
                            )}
                            <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded">
                              <FileCheck2 className="h-3 w-3" />
                              {conv.commitments_count || 0} Commitments
                            </span>
                          </div>

                          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                            <span>
                              {new Date(conv.recorded_at || conv.created_at).toLocaleDateString(
                                undefined,
                                { month: "short", day: "numeric" }
                              )}
                            </span>
                            <span className="group-hover:translate-x-0.5 transition-transform text-primary font-medium flex items-center gap-1">
                              View details <ArrowRight className="h-3 w-3" />
                            </span>
                          </div>
                        </CardContent>
                      </Card>
                    </Link>
                  );
                })
              )}
            </div>
          </section>
        </div>
      ) : (
        /* Unauthenticated Dynamic Product Showcase & Interactive Tour */
        <div className="space-y-6">
          <Card className="border shadow-sm overflow-hidden">
            <CardHeader className="bg-muted/30 border-b pb-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-primary" />
                  <div>
                    <CardTitle className="text-base font-bold">
                      Interactive Product Architecture & Tour
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Explore how FounderSignal connects audio evidence directly into actionable commitments.
                    </CardDescription>
                  </div>
                </div>

                {/* Tour Tab Switcher */}
                <div className="flex items-center gap-1 bg-background border p-1 rounded-lg text-xs">
                  <button
                    onClick={() => setPreviewTab("intake")}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      previewTab === "intake"
                        ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    1. Voice Intake
                  </button>
                  <button
                    onClick={() => setPreviewTab("commitments")}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      previewTab === "commitments"
                        ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    2. Signal Extraction
                  </button>
                  <button
                    onClick={() => setPreviewTab("isolation")}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      previewTab === "isolation"
                        ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    3. Tenant Isolation
                  </button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-6">
              {previewTab === "intake" && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                  <div className="space-y-3">
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-semibold">
                      <Zap className="h-3.5 w-3.5" /> High-Fidelity Audio Ingestion
                    </div>
                    <h3 className="text-xl font-bold tracking-tight">
                      Capture meetings, notes, and calls natively
                    </h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Record directly in modern browsers via MediaRecorder API in Opus/WebM, or upload WAV files. Magic-bytes headers and 25MB limits are verified before dispatching to Gnani Prisma STT.
                    </p>
                    <div className="flex items-center gap-3 pt-2">
                      <Button asChild size="sm">
                        <Link href="/register">Sign Up to Record</Link>
                      </Button>
                      <Button asChild variant="outline" size="sm">
                        <Link href="/login">Sign In</Link>
                      </Button>
                    </div>
                  </div>

                  {/* Simulated Waveform Visualizer */}
                  <div className="rounded-xl border bg-muted/30 p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                        <Volume2 className="h-4 w-4 text-primary" /> Live Audio Capture Simulation
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        audio/webm (48kHz)
                      </Badge>
                    </div>

                    <div className="h-14 flex items-center justify-center gap-1 px-4 bg-background rounded-lg border">
                      {[18, 35, 60, 85, 45, 95, 30, 70, 50, 80, 40, 65, 90, 30, 50, 75, 40, 25, 60, 45].map(
                        (height, idx) => (
                          <div
                            key={idx}
                            style={{ height: `${height}%` }}
                            className="w-1.5 rounded-full bg-primary/70 transition-all duration-300 hover:bg-primary"
                          />
                        )
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground text-center">
                      Streams directly to isolated tenant storage with cryptographic integrity.
                    </p>
                  </div>
                </div>
              )}

              {previewTab === "commitments" && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                  <div className="space-y-3">
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
                      <ShieldCheck className="h-3.5 w-3.5" /> Evidence Over Assumptions
                    </div>
                    <h3 className="text-xl font-bold tracking-tight">
                      Human approval for every business promise
                    </h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      AI never autonomously marks business promises as fact. The founder reviews extracted items with exact source quotation provenance and confidence scoring.
                    </p>
                    <div className="flex items-center gap-3 pt-2">
                      <Button asChild size="sm">
                        <Link href="/register">Test Drive Interactive Review</Link>
                      </Button>
                    </div>
                  </div>

                  {/* Interactive Demo Commitment Card */}
                  <div className="rounded-xl border bg-card p-4 shadow-sm space-y-3">
                    <div className="flex items-center justify-between">
                      <Badge
                        variant={demoApproved ? "success" : "warning"}
                        className="text-[10px] capitalize"
                      >
                        {demoApproved ? "Confirmed Commitment" : "Inferred Signal"}
                      </Badge>
                      <span className="text-[10px] font-semibold text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                        94% Confidence
                      </span>
                    </div>

                    <h4 className="text-sm font-semibold text-foreground">
                      Deliver client audit report by Friday 5 PM
                    </h4>

                    <div className="p-2.5 rounded-md bg-muted/40 border text-xs italic text-muted-foreground">
                      “I will prepare the complete onboarding metrics and delivery evidence by Friday.”
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <span className="text-[11px] text-muted-foreground">Speaker: Founder Nithesh</span>
                      <Button
                        size="sm"
                        variant={demoApproved ? "outline" : "default"}
                        onClick={() => setDemoApproved(!demoApproved)}
                        className="h-7 text-xs"
                      >
                        {demoApproved ? "Revoke Approval" : "Click to Approve (Demo)"}
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {previewTab === "isolation" && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div className="p-4 rounded-xl bg-muted/40 border space-y-2">
                    <div className="flex items-center gap-2">
                      <FolderGit2 className="h-4 w-4 text-primary" />
                      <span className="font-semibold text-foreground">Strict Tenant Isolation</span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Every database query, audio asset, and transcript strictly scoped by UUID workspace boundaries.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-muted/40 border space-y-2">
                    <div className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-emerald-500" />
                      <span className="font-semibold text-foreground">Cryptographic Hashes</span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      SHA-256 evidence fingerprints ensure quotes and commitment records cannot be tampered with.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-muted/40 border space-y-2">
                    <div className="flex items-center gap-2">
                      <Activity className="h-4 w-4 text-indigo-500" />
                      <span className="font-semibold text-foreground">PostgreSQL 16 & Alembic</span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Robust relational models, foreign key cascading, and zero schema drift across all environments.
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Roadmap & Next Phase Card (Retained for roadmap visibility) */}
      <Card className="border-dashed bg-muted/10">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">Phase 2A Foundation Verified</CardTitle>
          </div>
          <CardDescription>
            Secure audio intake, multi-tenant workspace isolation, and core data models are operational.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="p-4 rounded-lg bg-card border space-y-1 shadow-2xs">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <FolderGit2 className="h-4 w-4 text-primary" />
                Auth & Workspaces
              </span>
              <p className="text-xs text-muted-foreground">
                JWT auth, bcrypt hashing, token revocation, and strict cross-tenant isolation.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-card border space-y-1 shadow-2xs">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <CheckCircle className="h-4 w-4 text-emerald-500" />
                Audio Intake Storage
              </span>
              <p className="text-xs text-muted-foreground">
                Magic-bytes audio validation, 25MB limit enforcement, and traversal protection.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-card border space-y-1 shadow-2xs">
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
