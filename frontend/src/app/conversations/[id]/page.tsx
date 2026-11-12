"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Calendar,
  Clock,
  FileAudio,
  Loader2,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { AudioPlayer } from "@/components/audio-player";
import { CommitmentReview } from "@/components/commitment-review";
import { TranscriptView } from "@/components/transcript-view";
import { TranscriptionStatus } from "@/components/transcription-status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, ConversationDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function ConversationDetailPage() {
  const router = useRouter();
  const routeParams = useParams();
  const conversationId = typeof routeParams?.id === "string" ? routeParams.id : null;
  const { user, activeWorkspace, loading: authLoading } = useAuth();

  const [conversation, setConversation] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);


  const loadConversation = useCallback(async () => {
    if (!activeWorkspace || !conversationId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getConversation(activeWorkspace.id, conversationId);
      setConversation(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load conversation details.");
      }
    } finally {
      setLoading(false);
    }
  }, [activeWorkspace, conversationId]);

  useEffect(() => {
    if (activeWorkspace && conversationId) {
      loadConversation();
    } else if (!authLoading && !user) {
      setLoading(false);
    }
  }, [activeWorkspace, conversationId, authLoading, user, loadConversation]);

  const handleDelete = async () => {
    if (!activeWorkspace || !conversationId) return;
    if (!window.confirm("Are you sure you want to delete this conversation and its audio files?")) {
      return;
    }

    setDeleting(true);
    try {
      await api.deleteConversation(activeWorkspace.id, conversationId);
      router.push("/conversations");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to delete conversation.");
      }
      setDeleting(false);
    }
  };

  if (authLoading || (loading && !conversation)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3" data-testid="conversation-loading">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Loading conversation evidence...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-center max-w-md mx-auto p-6">
        <h2 className="text-xl font-bold tracking-tight mb-2">Authentication Required</h2>
        <p className="text-sm text-muted-foreground mb-6">
          Sign in to view transcripts, audio playback, and commitments.
        </p>
        <Button asChild>
          <Link href="/login">Sign In</Link>
        </Button>
      </div>
    );
  }

  if (error || !conversation) {
    return (
      <div className="max-w-2xl mx-auto space-y-4 py-8">
        <div className="p-4 rounded-xl bg-destructive/10 text-destructive text-sm border border-destructive/20">
          {error || "Conversation not found."}
        </div>
        <Button variant="outline" asChild className="gap-2">
          <Link href="/conversations">
            <ArrowLeft className="h-4 w-4" />
            Back to conversations
          </Link>
        </Button>
      </div>
    );
  }

  const primaryAudioAsset = conversation.audio_assets?.[0];
  const latestTranscript =
    conversation.transcripts && conversation.transcripts.length > 0
      ? conversation.transcripts[conversation.transcripts.length - 1]
      : null;

  return (
    <div className="space-y-6 max-w-5xl mx-auto" data-testid="conversation-detail-page">
      {/* Navigation & Header */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Button variant="ghost" size="sm" asChild className="gap-1.5 -ml-2 text-xs">
            <Link href="/conversations">
              <ArrowLeft className="h-4 w-4" />
              All conversations
            </Link>
          </Button>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadConversation}
              disabled={loading}
              className="h-8 text-xs gap-1.5"
              data-testid="refresh-conversation-btn"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDelete}
              disabled={deleting}
              className="h-8 text-xs text-destructive/80 hover:text-destructive hover:bg-destructive/10 gap-1.5"
              data-testid="delete-conversation-btn"
            >
              {deleting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              Delete
            </Button>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 border-b pb-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-xs uppercase tracking-wider font-semibold">
                {conversation.conversation_type}
              </Badge>
              <Badge
                variant={
                  conversation.status === "completed" || conversation.status === "uploaded"
                    ? "success"
                    : "secondary"
                }
                className="capitalize text-xs"
                data-testid="conversation-status-badge"
              >
                {conversation.status}
              </Badge>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground" data-testid="conversation-title">
              {conversation.title}
            </h1>
          </div>

          <div className="flex flex-col sm:items-end text-xs text-muted-foreground gap-1 font-mono">
            <span className="flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5" />
              {new Date(conversation.recorded_at || conversation.created_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
              })}
            </span>
            <span className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              {new Date(conversation.recorded_at || conversation.created_at).toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: Audio Playback & Transcription Pipeline */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column (1 col): Audio Player & Engine Status */}
        <div className="space-y-6 lg:col-span-1">
          {primaryAudioAsset ? (
            <>
              <AudioPlayer
                workspaceId={activeWorkspace!.id}
                conversationId={conversation.id}
                audioAsset={primaryAudioAsset}
              />

              <TranscriptionStatus
                workspaceId={activeWorkspace!.id}
                conversationId={conversation.id}
                audioAssetId={primaryAudioAsset.id}
                hasTranscript={Boolean(latestTranscript)}
                onTranscriptionComplete={loadConversation}
              />
            </>
          ) : (
            <Card className="border-dashed py-6 text-center">
              <CardContent className="space-y-2">
                <FileAudio className="h-8 w-8 text-muted-foreground mx-auto" />
                <p className="text-sm font-medium">No audio attached</p>
                <p className="text-xs text-muted-foreground">
                  This conversation has no audio file.
                </p>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right Column (2 cols): Transcript & Commitments Review */}
        <div className="space-y-6 lg:col-span-2">
          {latestTranscript && (
            <TranscriptView transcript={latestTranscript} />
          )}

          <CommitmentReview
            workspaceId={activeWorkspace!.id}
            conversationId={conversation.id}
            commitments={conversation.commitments || []}
            hasTranscript={Boolean(latestTranscript)}
            userRole={activeWorkspace?.role}
            onRefresh={loadConversation}
          />
        </div>
      </div>
    </div>
  );
}
