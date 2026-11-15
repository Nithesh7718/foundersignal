"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  Calendar,
  CheckCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  FolderKanban,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  api,
  Commitment,
  Project,
  ProjectDeliverySummary,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function ProjectsContent() {
  const { user, activeWorkspace, loading: authLoading } = useAuth();
  const searchParams = useSearchParams();

  // Workspace Data
  const [projects, setProjects] = useState<Project[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [deliverySummary, setDeliverySummary] = useState<ProjectDeliverySummary | null>(null);

  // Loading & error states
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  // Filters
  const [selectedProjectId, setSelectedProjectId] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Create Project Modal State
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDesc, setNewProjectDesc] = useState("");
  const [newProjectTargetDate, setNewProjectTargetDate] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);

  // Updating commitment or project
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  // Synchronize with URL query parameter if present
  useEffect(() => {
    const qProject = searchParams.get("project_id");
    if (qProject) {
      setSelectedProjectId(qProject);
    }
  }, [searchParams]);

  const loadData = useCallback(
    async (showRefreshIndicator = false) => {
      if (!activeWorkspace) return;
      if (showRefreshIndicator) {
        setIsRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      try {
        const [projList, commList, summary] = await Promise.all([
          api.listProjects(activeWorkspace.id).catch(() => [] as Project[]),
          api.listWorkspaceCommitments(activeWorkspace.id).catch(() => [] as Commitment[]),
          api.getDeliverySummary(activeWorkspace.id).catch(() => null),
        ]);

        setProjects(projList);
        setCommitments(commList);
        setDeliverySummary(summary);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load project delivery data.");
      } finally {
        setLoading(false);
        setIsRefreshing(false);
      }
    },
    [activeWorkspace]
  );

  useEffect(() => {
    if (activeWorkspace) {
      loadData();
    } else if (!authLoading && !user) {
      setLoading(false);
    }
  }, [activeWorkspace, authLoading, user, loadData]);

  // Handle Project Creation
  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace || !newProjectName.trim()) return;

    setCreatingProject(true);
    setError(null);

    try {
      const created = await api.createProject(activeWorkspace.id, {
        name: newProjectName.trim(),
        description: newProjectDesc.trim() || undefined,
        target_date: newProjectTargetDate ? new Date(newProjectTargetDate).toISOString() : undefined,
      });

      setProjects((prev) => [created, ...prev]);
      setIsCreateOpen(false);
      setNewProjectName("");
      setNewProjectDesc("");
      setNewProjectTargetDate("");
      setActionSuccessMsg(`Project "${created.name}" created successfully.`);
      setTimeout(() => setActionSuccessMsg(null), 3500);

      // Re-fetch summary in background
      api.getDeliverySummary(activeWorkspace.id).then(setDeliverySummary).catch(() => null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
    } finally {
      setCreatingProject(false);
    }
  };

  // Handle Commitment Project Reassignment
  const handleAssignProject = async (commitmentId: string, projectId: string | null) => {
    if (!activeWorkspace) return;
    setUpdatingId(commitmentId);

    try {
      const updated = await api.updateCommitment(activeWorkspace.id, commitmentId, {
        project_id: projectId,
      });

      setCommitments((prev) =>
        prev.map((c) => (c.id === commitmentId ? { ...c, project_id: updated.project_id } : c))
      );

      // Refresh projects list to update delivery counters
      const updatedProjects = await api.listProjects(activeWorkspace.id);
      setProjects(updatedProjects);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update project assignment.");
    } finally {
      setUpdatingId(null);
    }
  };

  // Handle Commitment Status Transition
  const handleUpdateStatus = async (commitmentId: string, newStatus: string) => {
    if (!activeWorkspace) return;
    setUpdatingId(commitmentId);

    try {
      const updated = await api.updateCommitment(activeWorkspace.id, commitmentId, {
        status: newStatus,
      });

      setCommitments((prev) =>
        prev.map((c) => (c.id === commitmentId ? { ...c, status: updated.status } : c))
      );

      // Refresh project delivery metrics
      const [updatedProjects, updatedSummary] = await Promise.all([
        api.listProjects(activeWorkspace.id),
        api.getDeliverySummary(activeWorkspace.id),
      ]);
      setProjects(updatedProjects);
      setDeliverySummary(updatedSummary);

      setActionSuccessMsg(`Commitment updated to ${newStatus.replace("_", " ")}.`);
      setTimeout(() => setActionSuccessMsg(null), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update commitment status.");
    } finally {
      setUpdatingId(null);
    }
  };

  // Filtered Commitments
  const filteredCommitments = useMemo(() => {
    return commitments.filter((comm) => {
      // Project filter
      if (selectedProjectId !== "all") {
        if (selectedProjectId === "unassigned") {
          if (comm.project_id) return false;
        } else if (comm.project_id !== selectedProjectId) {
          return false;
        }
      }

      // Status filter
      if (statusFilter !== "all" && comm.status !== statusFilter) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = comm.title.toLowerCase().includes(q);
        const matchesQuote = comm.source_quote.toLowerCase().includes(q);
        const matchesSpeaker = comm.speaker?.toLowerCase().includes(q) || false;
        return matchesTitle || matchesQuote || matchesSpeaker;
      }

      return true;
    });
  }, [commitments, selectedProjectId, statusFilter, searchQuery]);

  // Overdue commitments list
  const overdueCommitments = useMemo(() => {
    const now = new Date();
    return commitments.filter(
      (c) => c.due_date && new Date(c.due_date) < now && c.status !== "completed" && c.status !== "rejected"
    );
  }, [commitments]);

  if (authLoading || (loading && !activeWorkspace)) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <RefreshCw className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm font-medium">Loading projects & delivery cockpit...</p>
        </div>
      </div>
    );
  }

  if (!user || !activeWorkspace) {
    return (
      <div className="max-w-md mx-auto py-12 text-center space-y-4">
        <FolderKanban className="h-12 w-12 text-primary mx-auto" />
        <h2 className="text-xl font-bold">Authentication Required</h2>
        <p className="text-sm text-muted-foreground">
          Sign in to access your workspace delivery board, project milestones, and committed deliverables.
        </p>
        <Button asChild>
          <Link href="/login">Sign In</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16" data-testid="projects-page">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <FolderKanban className="h-6 w-6 text-primary" />
            Projects & Delivery Board
          </h1>
          <p className="text-sm text-muted-foreground">
            Track business deliverables, tie extracted commitments to core initiatives, and measure real progress.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadData(true)}
            disabled={isRefreshing}
            className="gap-2"
            data-testid="projects-refresh-btn"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => setIsCreateOpen(true)}
            className="gap-2"
            data-testid="open-create-project-btn"
          >
            <Plus className="h-4 w-4" />
            New Project
          </Button>
        </div>
      </div>

      {/* Global Alerts */}
      {actionSuccessMsg && (
        <div
          role="status"
          data-testid="projects-success-alert"
          className="p-3 text-sm rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center gap-2 border border-emerald-500/20"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{actionSuccessMsg}</span>
        </div>
      )}

      {error && (
        <div
          role="alert"
          data-testid="projects-error-alert"
          className="p-3 text-sm rounded-lg bg-destructive/10 text-destructive flex items-center gap-2 border border-destructive/20"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Delivery Metrics Overview Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="delivery-metrics-strip">
        <Card className="shadow-2xs">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Active Projects</CardDescription>
            <CardTitle className="text-2xl font-bold flex items-center justify-between">
              <span>{deliverySummary?.active_projects || 0}</span>
              <span className="text-xs font-normal text-muted-foreground">
                of {deliverySummary?.total_projects || 0} total
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
              <FolderKanban className="h-3.5 w-3.5 text-primary" />
              <span>{deliverySummary?.completed_projects || 0} projects completed</span>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-2xs">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Delivery Completion Rate</CardDescription>
            <CardTitle className="text-2xl font-bold flex items-center justify-between">
              <span>{deliverySummary?.delivery_completion_rate || 0}%</span>
              <TrendingUp className="h-5 w-5 text-emerald-500" />
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0 space-y-1.5">
            <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all duration-500"
                style={{ width: `${deliverySummary?.delivery_completion_rate || 0}%` }}
              />
            </div>
            <div className="text-[11px] text-muted-foreground">
              {deliverySummary?.completed_commitments || 0} of {deliverySummary?.total_commitments || 0} promises delivered
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-2xs">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">In-Progress Commitments</CardDescription>
            <CardTitle className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {deliverySummary?.in_progress_commitments || 0}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-blue-500" />
              <span>Actively executing deliverables</span>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-2xs">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Overdue Deliverables</CardDescription>
            <CardTitle className="text-2xl font-bold text-destructive">
              {overdueCommitments.length}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
              <ShieldAlert className="h-3.5 w-3.5 text-destructive" />
              <span>Past scheduled target date</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Modal / Dialog: Create New Project */}
      {isCreateOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4 animate-in fade-in duration-200"
          data-testid="create-project-modal"
        >
          <Card className="w-full max-w-lg shadow-2xl border-primary/20">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-lg">Create New Project</CardTitle>
                <CardDescription className="text-xs">
                  Group commitments, deliverables, and transcripts under a business objective.
                </CardDescription>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setIsCreateOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateProject} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="project-name">Project Name *</Label>
                  <Input
                    id="project-name"
                    placeholder="e.g. Q4 SOC2 Compliance Certification"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    required
                    data-testid="new-project-name-input"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="project-desc">Description</Label>
                  <textarea
                    id="project-desc"
                    rows={3}
                    placeholder="Brief objective, customer context, or expected outcome..."
                    value={newProjectDesc}
                    onChange={(e) => setNewProjectDesc(e.target.value)}
                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    data-testid="new-project-desc-input"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="project-date">Target Completion Date (Optional)</Label>
                  <Input
                    id="project-date"
                    type="date"
                    value={newProjectTargetDate}
                    onChange={(e) => setNewProjectTargetDate(e.target.value)}
                    data-testid="new-project-date-input"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsCreateOpen(false)}
                    disabled={creatingProject}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={creatingProject} data-testid="save-new-project-btn">
                    {creatingProject ? "Creating..." : "Create Project"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Projects Grid Section */}
      <section className="space-y-4" data-testid="projects-grid-section">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold tracking-tight text-foreground">Projects</h2>
            <Badge variant="outline">{projects.length}</Badge>
          </div>

          {selectedProjectId !== "all" && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedProjectId("all")}
              className="text-xs text-primary hover:underline h-7"
            >
              Clear Project Filter (Showing All)
            </Button>
          )}
        </div>

        {projects.length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center bg-card/40 space-y-3">
            <FolderKanban className="h-10 w-10 text-muted-foreground mx-auto" />
            <h3 className="font-semibold text-foreground">No Projects Created Yet</h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              Create initiatives to group commitments extracted from meetings and track cross-team delivery.
            </p>
            <Button size="sm" onClick={() => setIsCreateOpen(true)} className="gap-2">
              <Plus className="h-4 w-4" /> Create First Project
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => {
              const isSelected = selectedProjectId === project.id;
              const completionPercent =
                project.total_commitments > 0
                  ? Math.round((project.completed_commitments / project.total_commitments) * 100)
                  : 0;

              return (
                <Card
                  key={project.id}
                  onClick={() =>
                    setSelectedProjectId(isSelected ? "all" : project.id)
                  }
                  className={`cursor-pointer transition-all duration-200 shadow-2xs hover:shadow-md ${
                    isSelected
                      ? "ring-2 ring-primary border-primary bg-primary/5"
                      : "hover:border-primary/40 bg-card"
                  }`}
                  data-testid={`project-card-${project.id}`}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-base font-bold truncate">
                        {project.name}
                      </CardTitle>
                      <Badge
                        variant={project.status === "completed" ? "success" : "secondary"}
                        className="text-[10px] capitalize shrink-0"
                      >
                        {project.status}
                      </Badge>
                    </div>
                    {project.description && (
                      <CardDescription className="text-xs line-clamp-2">
                        {project.description}
                      </CardDescription>
                    )}
                  </CardHeader>
                  <CardContent className="space-y-3 text-xs">
                    {/* Progress Bar */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                        <span>Progress</span>
                        <span className="font-bold text-foreground">{completionPercent}%</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-300"
                          style={{ width: `${completionPercent}%` }}
                        />
                      </div>
                    </div>

                    {/* Breakdown Badges */}
                    <div className="flex items-center justify-between pt-1 text-[11px] text-muted-foreground">
                      <span>
                        <strong className="text-foreground">{project.total_commitments}</strong> deliverables
                      </span>
                      <span>
                        <strong className="text-emerald-600">{project.completed_commitments}</strong> completed
                      </span>
                      {project.overdue_commitments > 0 && (
                        <span className="text-destructive font-semibold">
                          {project.overdue_commitments} overdue
                        </span>
                      )}
                    </div>

                    {/* Target Date */}
                    {project.target_date && (
                      <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground pt-1 border-t">
                        <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>Target: {new Date(project.target_date).toLocaleDateString()}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* Deliverables & Commitments Board */}
      <section className="space-y-4" data-testid="commitments-board-section">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold tracking-tight text-foreground">
              Committed Deliverables
            </h2>
            <Badge variant="outline">{filteredCommitments.length}</Badge>
          </div>

          {/* Filtering toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search commitments..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 h-9 text-xs w-48 sm:w-60"
                data-testid="deliverables-search-input"
              />
            </div>

            {/* Filter by Project */}
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="flex h-9 rounded-md border border-input bg-background px-2.5 py-1 text-xs ring-offset-background"
              data-testid="deliverables-project-select"
            >
              <option value="all">All Projects</option>
              <option value="unassigned">Unassigned Deliverables</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>

            {/* Filter by Status */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="flex h-9 rounded-md border border-input bg-background px-2.5 py-1 text-xs ring-offset-background"
              data-testid="deliverables-status-select"
            >
              <option value="all">All Statuses</option>
              <option value="inferred">Inferred</option>
              <option value="confirmed">Confirmed</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
            </select>
          </div>
        </div>

        {filteredCommitments.length === 0 ? (
          <div className="p-8 text-center rounded-xl border bg-card text-muted-foreground text-xs">
            No commitments found matching current criteria.
          </div>
        ) : (
          <div className="space-y-3">
            {filteredCommitments.map((comm) => {
              const isOverdue =
                comm.due_date &&
                new Date(comm.due_date) < new Date() &&
                comm.status !== "completed" &&
                comm.status !== "rejected";

              return (
                <Card
                  key={comm.id}
                  className="shadow-2xs p-4 border bg-card hover:bg-muted/10 transition-colors"
                  data-testid={`commitment-row-${comm.id}`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="space-y-2 flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant={
                            comm.status === "completed"
                              ? "success"
                              : comm.status === "in_progress"
                              ? "default"
                              : comm.status === "confirmed"
                              ? "secondary"
                              : "warning"
                          }
                          className="capitalize text-[10px]"
                        >
                          {comm.status.replace("_", " ")}
                        </Badge>

                        {isOverdue && (
                          <Badge variant="destructive" className="text-[10px]">
                            Overdue
                          </Badge>
                        )}

                        {comm.confidence_score && (
                          <span className="text-[10px] text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-full font-mono font-medium">
                            {Math.round(comm.confidence_score * 100)}% Confidence
                          </span>
                        )}

                        {/* Project selector dropdown directly on commitment row */}
                        <div className="flex items-center gap-1.5 ml-auto sm:ml-0">
                          <FolderKanban className="h-3.5 w-3.5 text-muted-foreground" />
                          <select
                            value={comm.project_id || ""}
                            onChange={(e) =>
                              handleAssignProject(
                                comm.id,
                                e.target.value === "" ? null : e.target.value
                              )
                            }
                            disabled={updatingId === comm.id}
                            className="text-[11px] bg-background border rounded px-2 py-0.5 text-muted-foreground focus:text-foreground"
                            data-testid={`assign-project-select-${comm.id}`}
                          >
                            <option value="">Unassigned</option>
                            {projects.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <h4 className="text-sm font-bold text-foreground">
                        {comm.title}
                      </h4>

                      {/* Source Quotation Provenance */}
                      <div className="p-2.5 rounded-md bg-muted/40 border text-xs italic text-muted-foreground">
                        “{comm.source_quote}”
                      </div>

                      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-1">
                        {comm.speaker && (
                          <span>
                            <strong>Speaker:</strong> {comm.speaker}
                          </span>
                        )}
                        {comm.due_date && (
                          <span className={isOverdue ? "text-destructive font-semibold" : ""}>
                            <strong>Due:</strong> {new Date(comm.due_date).toLocaleDateString()}
                          </span>
                        )}
                        {comm.conversation_id && (
                          <Link
                            href={`/conversations/${comm.conversation_id}`}
                            className="inline-flex items-center gap-1 text-primary hover:underline ml-auto"
                            data-testid={`view-evidence-btn-${comm.id}`}
                          >
                            <span>Evidence Audio</span>
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        )}
                      </div>
                    </div>

                    {/* Quick Status Action Buttons */}
                    <div className="flex sm:flex-col items-center gap-1.5 shrink-0 self-end sm:self-start">
                      {comm.status === "inferred" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleUpdateStatus(comm.id, "confirmed")}
                          disabled={updatingId === comm.id}
                          className="h-7 text-xs gap-1"
                        >
                          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                          Confirm
                        </Button>
                      )}

                      {comm.status === "confirmed" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleUpdateStatus(comm.id, "in_progress")}
                          disabled={updatingId === comm.id}
                          className="h-7 text-xs gap-1 text-blue-600"
                        >
                          <Clock className="h-3.5 w-3.5" />
                          In Progress
                        </Button>
                      )}

                      {comm.status === "in_progress" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleUpdateStatus(comm.id, "completed")}
                          disabled={updatingId === comm.id}
                          className="h-7 text-xs gap-1 text-emerald-600"
                        >
                          <CheckCircle className="h-3.5 w-3.5" />
                          Complete
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

export default function ProjectsAndDeliveryPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[50vh]">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <RefreshCw className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm font-medium">Loading projects & delivery cockpit...</p>
          </div>
        </div>
      }
    >
      <ProjectsContent />
    </Suspense>
  );
}
