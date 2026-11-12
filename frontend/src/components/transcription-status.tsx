"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Cpu,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, TranscriptionJob } from "@/lib/api";

interface TranscriptionStatusProps {
  workspaceId: string;
  conversationId: string;
  audioAssetId: string;
  hasTranscript: boolean;
  onTranscriptionComplete: () => void;
}

export function TranscriptionStatus({
  workspaceId,
  conversationId,
  audioAssetId,
  hasTranscript,
  onTranscriptionComplete,
}: TranscriptionStatusProps) {
  const [jobs, setJobs] = useState<TranscriptionJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState("indic-auto");

  const latestJob = jobs.length > 0 ? jobs[0] : null;
  const isJobActive =
    latestJob &&
    [
      "queued",
      "submitting",
      "in_progress",
      "submitted",
      "processing",
    ].includes(latestJob.status);

  const fetchJobs = useCallback(async () => {
    try {
      const data = await api.listConversationTranscriptionJobs(
        workspaceId,
        conversationId
      );
      setJobs(data);

      const latest = data.length > 0 ? data[0] : null;
      if (latest && latest.status === "completed") {
        onTranscriptionComplete();
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [workspaceId, conversationId, onTranscriptionComplete]);

  // Initial load
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Polling while active
  useEffect(() => {
    if (!isJobActive) return;

    const timer = setInterval(() => {
      fetchJobs();
    }, 2000);

    return () => clearInterval(timer);
  }, [isJobActive, fetchJobs]);

  const handleStartTranscription = async () => {
    setTranscribing(true);
    setError(null);
    try {
      await api.createTranscriptionJob(
        workspaceId,
        conversationId,
        audioAssetId,
        selectedLanguage
      );
      await fetchJobs();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to trigger transcription.");
      }
    } finally {
      setTranscribing(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge variant="success">Completed</Badge>;
      case "in_progress":
      case "submitting":
      case "processing":
        return (
          <Badge variant="warning" className="gap-1 animate-pulse">
            <Loader2 className="h-3 w-3 animate-spin" /> In Progress
          </Badge>
        );
      case "queued":
        return (
          <Badge variant="secondary" className="gap-1">
            <Loader2 className="h-3 w-3 animate-spin" /> Queued
          </Badge>
        );
      case "submitted":
        return (
          <Badge variant="secondary" className="gap-1 animate-pulse">
            <Loader2 className="h-3 w-3 animate-spin" /> Batch Processing
          </Badge>
        );
      case "failed":
        return <Badge variant="destructive">Failed</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getStageDescription = (status: string) => {
    switch (status) {
      case "queued":
        return "Audio queued in processing pipeline. Worker claiming lease...";
      case "submitting":
      case "in_progress":
      case "processing":
        return "Converting speech to text via Gnani Prisma STT engine...";
      case "submitted":
        return "Processing long-form audio with Gnani Batch API...";
      case "completed":
        return "Transcription complete and verified with confidence rating.";
      case "failed":
        return "Transcription could not be completed.";
      default:
        return "";
    }
  };


  if (loading) {
    return (
      <Card className="border border-border/70 shadow-sm" data-testid="transcription-loading-card">
        <CardContent className="p-6 flex items-center justify-center space-x-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>Checking transcription status...</span>
        </CardContent>
      </Card>
    );
  }

  // Active transcription in progress
  if (isJobActive && latestJob) {
    const percent = Math.max(5, latestJob.progress_percent || 15);
    return (
      <Card className="border-primary/40 bg-primary/5 shadow-sm" data-testid="transcription-active-card">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="h-5 w-5 text-primary animate-pulse" />
              <CardTitle className="text-base font-semibold">
                Transcribing Audio
              </CardTitle>
            </div>
            {getStatusBadge(latestJob.status)}
          </div>
          <CardDescription className="text-xs">
            {getStageDescription(latestJob.status)}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Animated Progress Bar */}
          <div className="space-y-1">
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
                style={{ width: `${percent}%` }}
                data-testid="transcription-progress-bar"
              />
            </div>
            <div className="flex justify-between text-[11px] text-muted-foreground font-mono">
              <span>Engine: Gnani Prisma ({latestJob.job_type.toUpperCase()})</span>
              <span>{percent}%</span>
            </div>
          </div>

          <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
            <span>Job ID: {latestJob.id.slice(0, 8)}...</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchJobs}
              className="h-7 text-xs gap-1"
              data-testid="refresh-status-btn"
            >
              <RefreshCw className="h-3 w-3" /> Refresh
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Completed state
  if (hasTranscript || (latestJob && latestJob.status === "completed")) {
    return (
      <Card className="border-border/70 shadow-sm" data-testid="transcription-completed-card">
        <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
              <CheckCircle2 className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-medium leading-none">Transcription Verified</p>
              <p className="text-xs text-muted-foreground mt-1">
                Transcribed with Gnani Prisma STT ({latestJob?.language_code || "en"})
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleStartTranscription}
              disabled={transcribing}
              className="text-xs gap-1.5 h-8"
              data-testid="re-transcribe-btn"
            >
              {transcribing ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              Re-transcribe
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Not started or failed state: offer Transcribe Audio button
  return (
    <Card className="border border-border/80 shadow-sm" data-testid="transcription-trigger-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <CardTitle className="text-base font-semibold">
              Generate Transcript
            </CardTitle>
          </div>
          {latestJob && getStatusBadge(latestJob.status)}
        </div>
        <CardDescription className="text-xs">
          Process spoken audio through Gnani Prisma STT to produce an attributable transcript and extract commitments.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <div className="flex-1">
            <label className="text-xs font-medium text-muted-foreground block mb-1">
              Spoken Language
            </label>
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              data-testid="language-select"
            >
              <option value="indic-auto">Auto-detect (Indian English / Multi)</option>
              <option value="en">English (India / Global)</option>
              <option value="hi">Hindi (हिन्दी)</option>
              <option value="kn">Kannada (ಕನ್ನಡ)</option>
              <option value="ta">Tamil (தமிழ்)</option>
              <option value="te">Telugu (తెలుగు)</option>
            </select>
          </div>

          <div className="self-end w-full sm:w-auto">
            <Button
              type="button"
              onClick={handleStartTranscription}
              disabled={transcribing}
              className="w-full sm:w-auto gap-2"
              data-testid="start-transcription-btn"
            >
              {transcribing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Transcribe Audio
                </>
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
