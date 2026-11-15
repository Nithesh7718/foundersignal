"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Mic,
  Pause,
  Play,
  RotateCcw,
  Square,
  Trash2,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface SupportedAudioFormat {
  mimeType: string;
  extension: string;
}

export const PREFERRED_RECORDING_FORMATS: SupportedAudioFormat[] = [
  { mimeType: "audio/webm;codecs=opus", extension: "webm" },
  { mimeType: "audio/webm", extension: "webm" },
  { mimeType: "audio/ogg;codecs=opus", extension: "ogg" },
  { mimeType: "audio/ogg", extension: "ogg" },
  { mimeType: "audio/mp4", extension: "m4a" },
  { mimeType: "audio/aac", extension: "m4a" },
  { mimeType: "audio/wav", extension: "wav" },
];

export function detectSupportedRecordingFormat(): SupportedAudioFormat | null {
  if (typeof window === "undefined" || typeof window.MediaRecorder === "undefined") {
    return null;
  }

  for (const format of PREFERRED_RECORDING_FORMATS) {
    if (
      typeof MediaRecorder.isTypeSupported === "function" &&
      MediaRecorder.isTypeSupported(format.mimeType)
    ) {
      return format;
    }
  }

  // Fallback: If isTypeSupported is unsupported or returned false for all, return a default
  return { mimeType: "", extension: "webm" };
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export type RecordingState =
  | "idle"
  | "requesting_permission"
  | "recording"
  | "paused"
  | "stopped";

interface AudioRecorderProps {
  onRecordingComplete: (file: File, durationSeconds: number) => void;
  onRecordingDiscard: () => void;
  disabled?: boolean;
}

export function AudioRecorder({
  onRecordingComplete,
  onRecordingDiscard,
  disabled = false,
}: AudioRecorderProps) {
  const [recordingState, setRecordingState] = useState<RecordingState>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [recordedFile, setRecordedFile] = useState<File | null>(null);

  // Playback preview state
  const [isPreviewPlaying, setIsPreviewPlaying] = useState(false);
  const [previewCurrentTime, setPreviewCurrentTime] = useState(0);
  const [previewDuration, setPreviewDuration] = useState(0);
  const [isPreviewMuted, setIsPreviewMuted] = useState(false);

  // Refs for audio resources to prevent memory leaks and track sessions
  const streamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  // Stop and release all microphone tracks immediately
  const stopMicrophoneTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch {
          // Ignore errors during track cleanup
        }
      });
      streamRef.current = null;
    }
  }, []);

  // Revoke object URL to avoid browser memory leaks
  const revokeObjectUrl = useCallback(() => {
    if (objectUrlRef.current) {
      try {
        URL.revokeObjectURL(objectUrlRef.current);
      } catch {
        // Ignore errors during object URL revocation
      }
      objectUrlRef.current = null;
    }
  }, []);

  // Clear timer
  const stopTimer = useCallback(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
  }, []);

  // Full unmount cleanup
  useEffect(() => {
    return () => {
      stopMicrophoneTracks();
      revokeObjectUrl();
      stopTimer();
    };
  }, [stopMicrophoneTracks, revokeObjectUrl, stopTimer]);

  // Handle browser window close / reload warning if recording is active
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (recordingState === "recording" || recordingState === "paused") {
        e.preventDefault();
        e.returnValue = "A recording is in progress. Are you sure you want to leave?";
        return e.returnValue;
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [recordingState]);

  // Start recording handler
  const handleStartRecording = async () => {
    setErrorMessage(null);

    // 1. Verify browser supports MediaRecorder
    if (
      typeof window === "undefined" ||
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== "function" ||
      typeof window.MediaRecorder === "undefined"
    ) {
      setErrorMessage(
        "Audio recording is not supported in this browser. Please use a modern browser (Chrome, Firefox, Safari, Edge) or upload a file directly."
      );
      return;
    }

    // 2. Identify supported MIME type
    const format = detectSupportedRecordingFormat();
    if (!format) {
      setErrorMessage(
        "No supported audio recording format was detected in this browser."
      );
      return;
    }

    // 3. Request microphone access only upon user action
    setRecordingState("requesting_permission");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (err: unknown) {
      setRecordingState("idle");
      if (err instanceof DOMException || (err && typeof err === "object" && "name" in err)) {
        const errorName = (err as { name: string }).name;
        if (errorName === "NotAllowedError" || errorName === "PermissionDeniedError") {
          setErrorMessage(
            "Microphone permission was denied. Please allow microphone access in your browser settings to record audio."
          );
        } else if (errorName === "NotFoundError" || errorName === "DevicesNotFoundError") {
          setErrorMessage(
            "No microphone was detected on your device. Please plug in or connect a microphone and try again."
          );
        } else if (errorName === "NotReadableError" || errorName === "TrackStartError") {
          setErrorMessage(
            "Microphone is currently unavailable. It might be in use by another application or video call."
          );
        } else if (errorName === "NotSupportedError") {
          setErrorMessage(
            "Microphone access constraints are not supported by this browser."
          );
        } else {
          setErrorMessage(`Microphone access error: ${(err as Error).message || errorName}`);
        }
      } else {
        setErrorMessage("Failed to access your microphone.");
      }
      return;
    }

    // 4. Initialize MediaRecorder instance
    try {
      stopMicrophoneTracks();
      revokeObjectUrl();
      streamRef.current = stream;
      audioChunksRef.current = [];

      const recorderOptions: MediaRecorderOptions = {};
      if (format.mimeType) {
        recorderOptions.mimeType = format.mimeType;
      }

      const recorder = new MediaRecorder(stream, recorderOptions);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setErrorMessage("A recording error occurred. Please try again.");
        stopMicrophoneTracks();
        stopTimer();
        setRecordingState("idle");
      };

      recorder.onstop = () => {
        stopMicrophoneTracks();
        stopTimer();

        const chunks = audioChunksRef.current;
        if (!chunks || chunks.length === 0) {
          setErrorMessage("Recording was empty. No audio was captured.");
          setRecordingState("idle");
          return;
        }

        const rawMime = format.mimeType ? format.mimeType.split(";")[0] : "audio/webm";
        const recordedBlob = new Blob(chunks, { type: rawMime });

        if (recordedBlob.size === 0) {
          setErrorMessage("Recording was empty (0 bytes). Please check your microphone input level.");
          setRecordingState("idle");
          return;
        }

        // Package as a proper File object matching real format and extension
        const now = new Date();
        const timestamp = now
          .toISOString()
          .replace(/[-:T]/g, "")
          .slice(0, 14);
        const ext = format.extension || "webm";
        const filename = `recording_${timestamp}.${ext}`;
        const file = new File([recordedBlob], filename, {
          type: rawMime,
          lastModified: Date.now(),
        });

        // Generate Object URL for immediate user playback preview
        const url = URL.createObjectURL(recordedBlob);
        revokeObjectUrl();
        objectUrlRef.current = url;
        setAudioUrl(url);
        setRecordedFile(file);
        setRecordingState("stopped");
        setIsPreviewPlaying(false);

        // Notify parent form of the new recording
        onRecordingComplete(file, elapsedSeconds);
      };

      // Start recording
      recorder.start(250); // Emit 250ms chunks to ensure continuous data gathering
      setRecordingState("recording");
      setElapsedSeconds(0);

      // Start duration timer
      stopTimer();
      timerIntervalRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: unknown) {
      stopMicrophoneTracks();
      stopTimer();
      setRecordingState("idle");
      if (err instanceof Error) {
        setErrorMessage(`Failed to start recording: ${err.message}`);
      } else {
        setErrorMessage("Failed to start audio recording.");
      }
    }
  };

  // Pause recording handler
  const handlePauseRecording = () => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording" &&
      recordingState === "recording"
    ) {
      try {
        mediaRecorderRef.current.pause();
        stopTimer();
        setRecordingState("paused");
      } catch {
        setErrorMessage("Failed to pause recording.");
      }
    }
  };

  // Resume recording handler
  const handleResumeRecording = () => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "paused" &&
      recordingState === "paused"
    ) {
      try {
        mediaRecorderRef.current.resume();
        setRecordingState("recording");
        stopTimer();
        timerIntervalRef.current = setInterval(() => {
          setElapsedSeconds((prev) => prev + 1);
        }, 1000);
      } catch {
        setErrorMessage("Failed to resume recording.");
      }
    }
  };

  // Stop recording handler
  const handleStopRecording = () => {
    if (
      mediaRecorderRef.current &&
      (mediaRecorderRef.current.state === "recording" ||
        mediaRecorderRef.current.state === "paused")
    ) {
      try {
        mediaRecorderRef.current.stop();
        // mediaRecorder.onstop handles state transitions & URL creation
      } catch {
        stopMicrophoneTracks();
        stopTimer();
        setErrorMessage("Failed to stop recording cleanly.");
        setRecordingState("idle");
      }
    }
  };

  // Delete recording handler
  const handleDeleteRecording = () => {
    stopMicrophoneTracks();
    revokeObjectUrl();
    stopTimer();
    setRecordingState("idle");
    setElapsedSeconds(0);
    setAudioUrl(null);
    setRecordedFile(null);
    setIsPreviewPlaying(false);
    setPreviewCurrentTime(0);
    setPreviewDuration(0);
    setErrorMessage(null);
    onRecordingDiscard();
  };

  // Re-record handler (discards current recording and immediately prompts ready)
  const handleRerecord = () => {
    handleDeleteRecording();
  };

  // Preview playback controls
  const togglePreviewPlay = () => {
    if (!previewAudioRef.current) return;
    if (isPreviewPlaying) {
      previewAudioRef.current.pause();
      setIsPreviewPlaying(false);
    } else {
      previewAudioRef.current.play().catch(() => {
        setIsPreviewPlaying(false);
      });
      setIsPreviewPlaying(true);
    }
  };

  return (
    <div className="space-y-4" data-testid="audio-recorder-container">
      {/* Error alert */}
      {errorMessage && (
        <div
          role="alert"
          data-testid="recording-error-alert"
          className="p-3 text-xs rounded-lg bg-destructive/10 text-destructive flex items-start gap-2 border border-destructive/20"
        >
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Microphone Error: </span>
            <span>{errorMessage}</span>
          </div>
        </div>
      )}

      {/* Main recording control card */}
      <div className="border rounded-xl p-5 bg-card/60 space-y-4">
        {/* Status header with live indicator */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {recordingState === "recording" && (
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
              </span>
            )}
            {recordingState === "paused" && (
              <span className="inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
            )}
            {recordingState === "idle" && (
              <span className="inline-flex rounded-full h-3 w-3 bg-muted-foreground/40"></span>
            )}
            {recordingState === "stopped" && (
              <span className="inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            )}

            <Badge
              variant={
                recordingState === "recording"
                  ? "destructive"
                  : recordingState === "paused"
                  ? "warning"
                  : recordingState === "stopped"
                  ? "success"
                  : "outline"
              }
              className="text-xs uppercase tracking-wider font-semibold"
              data-testid="recording-status-badge"
            >
              {recordingState === "idle" && "Ready to record"}
              {recordingState === "requesting_permission" && "Requesting mic..."}
              {recordingState === "recording" && "Recording audio"}
              {recordingState === "paused" && "Recording paused"}
              {recordingState === "stopped" && "Recording ready"}
            </Badge>
          </div>

          {/* Duration timer */}
          <div
            className="font-mono text-sm font-semibold tracking-wider text-foreground"
            data-testid="recording-timer"
          >
            {formatDuration(elapsedSeconds)}
          </div>
        </div>

        {/* Dynamic Controls based on recording state */}
        <div className="flex flex-col items-center justify-center py-4 space-y-4">
          {/* Idle State: Big Record Button */}
          {recordingState === "idle" && (
            <div className="text-center space-y-3">
              <Button
                type="button"
                size="lg"
                onClick={handleStartRecording}
                disabled={disabled}
                className="h-16 w-16 rounded-full bg-red-600 hover:bg-red-700 text-white shadow-lg transition-transform hover:scale-105 active:scale-95"
                data-testid="start-recording-btn"
                aria-label="Start recording audio"
              >
                <Mic className="h-7 w-7" />
              </Button>
              <div className="space-y-1">
                <p className="text-sm font-medium">Click microphone to start recording</p>
                <p className="text-xs text-muted-foreground">
                  Browser will request microphone permission.
                </p>
              </div>
            </div>
          )}

          {/* Requesting Permission */}
          {recordingState === "requesting_permission" && (
            <div className="text-center py-4 space-y-2">
              <div className="inline-block animate-pulse h-12 w-12 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto">
                <Mic className="h-6 w-6" />
              </div>
              <p className="text-sm font-medium">Please grant microphone permission in your browser prompt...</p>
            </div>
          )}

          {/* Active Recording or Paused State */}
          {(recordingState === "recording" || recordingState === "paused") && (
            <div className="w-full max-w-sm space-y-4">
              <div className="flex items-center justify-center gap-4">
                {recordingState === "recording" ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handlePauseRecording}
                    className="gap-2"
                    data-testid="pause-recording-btn"
                  >
                    <Pause className="h-4 w-4" />
                    Pause
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleResumeRecording}
                    className="gap-2 text-primary"
                    data-testid="resume-recording-btn"
                  >
                    <Play className="h-4 w-4" />
                    Resume
                  </Button>
                )}

                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={handleStopRecording}
                  className="gap-2"
                  data-testid="stop-recording-btn"
                >
                  <Square className="h-4 w-4 fill-current" />
                  Stop Recording
                </Button>
              </div>

              <p className="text-center text-xs text-muted-foreground">
                {recordingState === "recording"
                  ? "Speaking now... click Stop when you finish."
                  : "Recording paused. Click Resume to continue speaking."}
              </p>
            </div>
          )}

          {/* Stopped / Recorded Preview State */}
          {recordingState === "stopped" && audioUrl && recordedFile && (
            <div
              className="w-full space-y-4 pt-1"
              data-testid="audio-preview-player"
            >
              {/* Native audio element (hidden, driven by UI) */}
              <audio
                ref={previewAudioRef}
                src={audioUrl}
                preload="metadata"
                onTimeUpdate={() => {
                  if (previewAudioRef.current) {
                    setPreviewCurrentTime(previewAudioRef.current.currentTime);
                  }
                }}
                onLoadedMetadata={() => {
                  if (previewAudioRef.current) {
                    setPreviewDuration(previewAudioRef.current.duration || elapsedSeconds);
                  }
                }}
                onEnded={() => {
                  setIsPreviewPlaying(false);
                  setPreviewCurrentTime(0);
                }}
                className="hidden"
              />

              {/* Preview Player Bar */}
              <div className="p-3 rounded-lg bg-background border flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="flex items-center gap-3 w-full sm:w-auto">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={togglePreviewPlay}
                    className="h-9 w-9 p-0 rounded-full bg-primary/10 text-primary hover:bg-primary/20"
                    data-testid="audio-preview-play-btn"
                    aria-label={isPreviewPlaying ? "Pause preview" : "Play preview"}
                  >
                    {isPreviewPlaying ? (
                      <Pause className="h-4 w-4" />
                    ) : (
                      <Play className="h-4 w-4 ml-0.5" />
                    )}
                  </Button>

                  <div className="truncate">
                    <p className="text-xs font-semibold truncate text-foreground">
                      {recordedFile.name}
                    </p>
                    <p className="text-[11px] text-muted-foreground font-mono">
                      {formatDuration(previewCurrentTime)} / {formatDuration(previewDuration || elapsedSeconds)} •{" "}
                      {(recordedFile.size / (1024 * 1024)).toFixed(2)} MB
                    </p>
                  </div>
                </div>

                {/* Scrubber slider */}
                <div className="flex-1 w-full max-w-xs flex items-center gap-2">
                  <input
                    type="range"
                    min="0"
                    max={previewDuration || elapsedSeconds || 1}
                    step="0.1"
                    value={previewCurrentTime}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      setPreviewCurrentTime(val);
                      if (previewAudioRef.current) {
                        previewAudioRef.current.currentTime = val;
                      }
                    }}
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    aria-label="Audio preview scrubber"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (previewAudioRef.current) {
                        previewAudioRef.current.muted = !isPreviewMuted;
                        setIsPreviewMuted(!isPreviewMuted);
                      }
                    }}
                    className="h-7 w-7 p-0 text-muted-foreground"
                    aria-label={isPreviewMuted ? "Unmute" : "Mute"}
                  >
                    {isPreviewMuted ? (
                      <VolumeX className="h-3.5 w-3.5" />
                    ) : (
                      <Volume2 className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>

                {/* Re-record & Delete actions */}
                <div className="flex items-center gap-1.5 w-full sm:w-auto justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleRerecord}
                    className="h-8 text-xs gap-1.5"
                    data-testid="rerecord-btn"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Re-record
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleDeleteRecording}
                    className="h-8 text-xs text-destructive hover:bg-destructive/10 gap-1.5"
                    data-testid="delete-recording-btn"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
