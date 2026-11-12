"use client";

import React, { useState } from "react";
import {
  Check,
  Copy,
  FileText,
  Quote,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Transcript } from "@/lib/api";

interface TranscriptViewProps {
  transcript: Transcript;
}

export function TranscriptView({ transcript }: TranscriptViewProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(transcript.raw_transcript);
      } else {
        throw new Error("Clipboard API not available");
      }
    } catch {
      try {
        const textarea = document.createElement("textarea");
        textarea.value = transcript.raw_transcript;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      } catch {
        // Ignore fallback error
      }
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };


  const confidencePct =
    transcript.confidence !== undefined && transcript.confidence !== null
      ? Math.round(transcript.confidence * 100)
      : null;

  return (
    <Card className="border border-border/80 shadow-sm" data-testid="transcript-card">
      <CardHeader className="pb-3 border-b bg-muted/20">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <FileText className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-base font-semibold leading-tight">
                Transcript
              </CardTitle>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-muted-foreground">
                  Engine: <span className="font-medium text-foreground">{transcript.provider.replace("_", " ")}</span>
                </span>
                {transcript.language_code && (
                  <span className="text-xs text-muted-foreground uppercase font-mono">
                    &bull; {transcript.language_code}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {confidencePct !== null && (
              <Badge
                variant={confidencePct >= 80 ? "success" : "warning"}
                className="gap-1 font-mono text-xs"
                data-testid="transcript-confidence-badge"
              >
                <Sparkles className="h-3 w-3" />
                {confidencePct}% Transcription Confidence
              </Badge>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="gap-1.5 text-xs h-8"
              data-testid="copy-transcript-btn"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-600" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  Copy
                </>
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6">
        {transcript.raw_transcript.trim() ? (
          <div className="relative">
            <Quote className="h-8 w-8 text-muted-foreground/15 absolute -top-2 -left-2 -z-0 pointer-events-none" />
            <div
              className="relative z-10 text-sm leading-relaxed text-foreground whitespace-pre-wrap font-normal"
              data-testid="transcript-text"
            >
              {transcript.raw_transcript}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground italic" data-testid="transcript-empty-text">
            (No speech detected in this audio recording)
          </p>
        )}
      </CardContent>
    </Card>
  );
}
