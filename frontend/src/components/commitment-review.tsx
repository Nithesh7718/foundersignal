"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Edit2,
  Filter,
  Loader2,
  Quote,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, Commitment } from "@/lib/api";

interface CommitmentReviewProps {
  workspaceId: string;
  conversationId: string;
  commitments: Commitment[];
  hasTranscript: boolean;
  userRole?: string;
  onRefresh: () => void;
}

export function CommitmentReview({
  workspaceId,
  conversationId,
  commitments,
  hasTranscript,
  userRole,
  onRefresh,
}: CommitmentReviewProps) {
  const isPrivileged = !userRole || userRole === "owner" || userRole === "admin";
  const canEditOrExtract = !userRole || userRole === "owner" || userRole === "admin" || userRole === "member";
  const [filter, setFilter] = useState<"all" | "inferred" | "confirmed" | "rejected">("all");
  const [extracting, setExtracting] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Editing state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");

  const handleExtract = async () => {
    setExtracting(true);
    setError(null);
    try {
      await api.extractCommitments(workspaceId, conversationId);
      onRefresh();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to extract commitments.");
      }
    } finally {
      setExtracting(false);
    }
  };

  const handleUpdateStatus = async (commitmentId: string, newStatus: string) => {
    setActionLoadingId(commitmentId);
    setError(null);
    try {
      await api.updateCommitment(workspaceId, commitmentId, { status: newStatus });
      onRefresh();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to update commitment status.");
      }
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleSaveEdit = async (commitmentId: string) => {
    setActionLoadingId(commitmentId);
    setError(null);
    try {
      await api.updateCommitment(workspaceId, commitmentId, {
        title: editTitle,
        description: editDesc,
      });
      setEditingId(null);
      onRefresh();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to save commitment changes.");
      }
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDelete = async (commitmentId: string) => {
    if (!window.confirm("Are you sure you want to delete this commitment?")) return;
    setActionLoadingId(commitmentId);
    setError(null);
    try {
      await api.deleteCommitment(workspaceId, commitmentId);
      onRefresh();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to delete commitment.");
      }
    } finally {
      setActionLoadingId(null);
    }
  };

  const startEditing = (c: Commitment) => {
    setEditingId(c.id);
    setEditTitle(c.title);
    setEditDesc(c.description || "");
  };

  const filteredCommitments = commitments.filter((c) => {
    if (filter === "all") return true;
    return c.status === filter;
  });

  const pendingCount = commitments.filter((c) => c.status === "inferred").length;
  const confirmedCount = commitments.filter((c) => c.status === "confirmed").length;

  return (
    <div className="space-y-4" data-testid="commitment-review-section">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-bold tracking-tight text-foreground">
              Commitments & Decisions
            </h2>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            AI-extracted commitments require explicit founder approval before becoming operational records.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {hasTranscript && (
            <Button
              onClick={handleExtract}
              disabled={extracting || !canEditOrExtract}
              size="sm"
              className="gap-1.5 h-8 text-xs"
              data-testid="extract-commitments-btn"
              title={!canEditOrExtract ? "Viewers cannot extract commitments" : undefined}
            >
              {extracting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Extracting...
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  Extract Commitments
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Filter Tabs */}
      {commitments.length > 0 && (
        <div className="flex items-center gap-2 border-b pb-2 text-xs">
          <Filter className="h-3.5 w-3.5 text-muted-foreground mr-1" />
          <Button
            variant={filter === "all" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setFilter("all")}
            className="h-7 text-xs font-normal"
            data-testid="filter-all"
          >
            All ({commitments.length})
          </Button>
          <Button
            variant={filter === "inferred" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setFilter("inferred")}
            className="h-7 text-xs font-normal text-amber-600 dark:text-amber-400 gap-1.5"
            data-testid="filter-inferred"
          >
            <Clock className="h-3 w-3" />
            Pending Review ({pendingCount})
          </Button>
          <Button
            variant={filter === "confirmed" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setFilter("confirmed")}
            className="h-7 text-xs font-normal text-emerald-600 dark:text-emerald-400 gap-1.5"
            data-testid="filter-confirmed"
          >
            <CheckCircle2 className="h-3 w-3" />
            Confirmed ({confirmedCount})
          </Button>
          <Button
            variant={filter === "rejected" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setFilter("rejected")}
            className="h-7 text-xs font-normal text-muted-foreground"
            data-testid="filter-rejected"
          >
            Rejected
          </Button>
        </div>
      )}

      {/* Commitments List */}
      {commitments.length === 0 ? (
        <Card className="border-dashed py-8 text-center" data-testid="commitments-empty-card">
          <CardHeader className="space-y-2 pb-2">
            <div className="mx-auto h-10 w-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <CardTitle className="text-base">No commitments extracted yet</CardTitle>
            <CardDescription className="text-xs max-w-sm mx-auto">
              {hasTranscript
                ? "Click 'Extract Commitments' above to scan the transcript for commitments, decisions, and action items."
                : "Generate a transcript first to extract business commitments and trackable execution signals."}
            </CardDescription>
          </CardHeader>
          {hasTranscript && (
            <CardContent>
              <Button
                size="sm"
                onClick={handleExtract}
                disabled={extracting || !canEditOrExtract}
                className="gap-1.5 text-xs"
                data-testid="extract-first-commitments-btn"
                title={!canEditOrExtract ? "Viewers cannot extract commitments" : undefined}
              >
                <Sparkles className="h-3.5 w-3.5" />
                Extract Commitments from Transcript
              </Button>
            </CardContent>
          )}
        </Card>
      ) : filteredCommitments.length === 0 ? (
        <div className="p-8 text-center text-xs text-muted-foreground bg-muted/20 rounded-lg border">
          No commitments found matching the selected filter.
        </div>
      ) : (
        <div className="grid gap-3" data-testid="commitments-list">
          {filteredCommitments.map((c) => {
            const isEditing = editingId === c.id;
            const isActing = actionLoadingId === c.id;
            const confidencePct =
              c.confidence_score !== null && c.confidence_score !== undefined
                ? Math.round(c.confidence_score * 100)
                : null;

            return (
              <Card
                key={c.id}
                className={`transition-colors shadow-sm ${
                  c.status === "inferred"
                    ? "border-amber-500/30 bg-amber-500/5 dark:bg-amber-950/10"
                    : c.status === "confirmed"
                    ? "border-emerald-500/30 bg-emerald-500/5 dark:bg-emerald-950/10"
                    : "border-border/60 opacity-80"
                }`}
                data-testid={`commitment-card-${c.id}`}
              >
                <CardContent className="p-4 space-y-3">
                  {/* Status header */}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {c.status === "inferred" && (
                        <Badge variant="warning" className="gap-1 text-[11px]" data-testid="badge-inferred">
                          <Clock className="h-3 w-3" />
                          Pending Founder Review
                        </Badge>
                      )}
                      {c.status === "confirmed" && (
                        <Badge variant="success" className="gap-1 text-[11px]" data-testid="badge-confirmed">
                          <CheckCircle2 className="h-3 w-3" />
                          Confirmed Fact
                        </Badge>
                      )}
                      {c.status === "rejected" && (
                        <Badge variant="destructive" className="gap-1 text-[11px]" data-testid="badge-rejected">
                          <X className="h-3 w-3" />
                          Rejected
                        </Badge>
                      )}
                      {c.status === "completed" && (
                        <Badge variant="default" className="text-[11px]">
                          Completed
                        </Badge>
                      )}

                      {confidencePct !== null ? (
                        <Badge variant="outline" className="text-[11px] font-mono">
                          {confidencePct}% Extraction Confidence
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-[11px] text-muted-foreground">
                          Confidence unavailable
                        </Badge>
                      )}
                    </div>

                    {/* Operational controls */}
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => (isEditing ? setEditingId(null) : startEditing(c))}
                        disabled={!canEditOrExtract}
                        className="h-7 w-7 p-0"
                        title={!canEditOrExtract ? "Viewers cannot edit commitments" : "Edit commitment"}
                        data-testid={`edit-commitment-btn-${c.id}`}
                      >
                        <Edit2 className="h-3.5 w-3.5 text-muted-foreground" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(c.id)}
                        disabled={!isPrivileged}
                        className="h-7 w-7 p-0"
                        title={!isPrivileged ? "Only workspace owners and admins can delete commitments" : "Delete commitment"}
                        data-testid={`delete-commitment-btn-${c.id}`}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive/70 hover:text-destructive" />
                      </Button>
                    </div>
                  </div>

                  {/* Body / Edit form */}
                  {isEditing ? (
                    <div className="space-y-2 pt-1">
                      <Input
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        placeholder="Commitment title"
                        className="text-sm font-semibold"
                        data-testid="edit-title-input"
                      />
                      <Input
                        value={editDesc}
                        onChange={(e) => setEditDesc(e.target.value)}
                        placeholder="Actionable description or next step"
                        className="text-xs"
                        data-testid="edit-desc-input"
                      />
                      <div className="flex gap-2 justify-end pt-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditingId(null)}
                          className="h-7 text-xs"
                        >
                          Cancel
                        </Button>
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => handleSaveEdit(c.id)}
                          disabled={isActing}
                          className="h-7 text-xs"
                          data-testid="save-edit-btn"
                        >
                          {isActing ? <Loader2 className="h-3 w-3 animate-spin" /> : "Save Changes"}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <h3 className="text-sm font-semibold text-foreground leading-snug" data-testid="commitment-title">
                        {c.title}
                      </h3>
                      {c.description && (
                        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                          {c.description}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Source Evidence Box (Principle 1 & 3) */}
                  <div className="rounded-md bg-background/80 border p-2.5 text-xs space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <span className="font-semibold uppercase tracking-wider flex items-center gap-1 text-[10px]">
                        <Quote className="h-3 w-3 text-primary" />
                        Source Evidence
                      </span>
                      {c.speaker && (
                        <span className="flex items-center gap-1 font-medium text-foreground">
                          <User className="h-3 w-3" />
                          {c.speaker}
                        </span>
                      )}
                    </div>
                    <blockquote
                      className="italic text-foreground/90 pl-2 border-l-2 border-primary/40 leading-relaxed font-serif"
                      data-testid="source-quote"
                    >
                      &ldquo;{c.source_quote}&rdquo;
                    </blockquote>
                  </div>

                  {/* Review Actions (Principle 2: Human Approval) */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-border/40">
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {new Date(c.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {!isPrivileged && (
                        <span className="text-[11px] text-muted-foreground italic" data-testid="rbac-approval-note">
                          Approval actions require owner or admin role
                        </span>
                      )}
                      {c.status === "inferred" && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleUpdateStatus(c.id, "rejected")}
                            disabled={isActing || !isPrivileged}
                            title={!isPrivileged ? "Only workspace owners and admins can reject commitments" : undefined}
                            className="h-7 text-xs text-muted-foreground hover:text-destructive gap-1"
                            data-testid={`reject-btn-${c.id}`}
                          >
                            <X className="h-3 w-3" />
                            Reject
                          </Button>
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() => handleUpdateStatus(c.id, "confirmed")}
                            disabled={isActing || !isPrivileged}
                            title={!isPrivileged ? "Only workspace owners and admins can confirm commitments" : undefined}
                            className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700 text-white gap-1"
                            data-testid={`confirm-btn-${c.id}`}
                          >
                            {isActing ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Check className="h-3 w-3" />
                            )}
                            Confirm & Approve
                          </Button>
                        </>
                      )}

                      {c.status === "confirmed" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleUpdateStatus(c.id, "completed")}
                          disabled={isActing || !canEditOrExtract}
                          className="h-7 text-xs text-primary gap-1"
                          data-testid={`complete-btn-${c.id}`}
                        >
                          <CheckCircle2 className="h-3 w-3" />
                          Mark Completed
                        </Button>
                      )}

                      {c.status === "rejected" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleUpdateStatus(c.id, "inferred")}
                          disabled={isActing || !isPrivileged}
                          title={!isPrivileged ? "Only workspace owners and admins can reopen commitments" : undefined}
                          className="h-7 text-xs text-muted-foreground"
                          data-testid={`restore-btn-${c.id}`}
                        >
                          Reopen Review
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
