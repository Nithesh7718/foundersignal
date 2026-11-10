"use client";

import React, { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  FileAudio,
  Mic,
  UploadCloud,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const ALLOWED_EXTENSIONS = [".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm"];
const MAX_FILE_SIZE_MB = 25;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export default function NewConversationPage() {
  const router = useRouter();
  const { user, activeWorkspace, loading: authLoading } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState("");
  const [conversationType, setConversationType] = useState("voice_note");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<
    "idle" | "creating" | "uploading" | "success" | "error"
  >("idle");

  const validateFile = (file: File): string | null => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported file format. Please upload an audio file (${ALLOWED_EXTENSIONS.join(", ")}).`;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return `File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds the maximum limit of ${MAX_FILE_SIZE_MB}MB.`;
    }
    return null;
  };

  const handleFileSelect = (file: File) => {
    setError(null);
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!activeWorkspace) {
      setError("Please select or create an active workspace before uploading.");
      return;
    }

    if (!title.trim()) {
      setError("Please provide a title for this conversation.");
      return;
    }

    if (!selectedFile) {
      setError("Please select an audio file to upload.");
      return;
    }

    try {
      setUploadStatus("creating");
      const conversation = await api.createConversation(activeWorkspace.id, {
        title: title.trim(),
        conversation_type: conversationType,
      });

      setUploadStatus("uploading");
      await api.uploadAudio(activeWorkspace.id, conversation.id, selectedFile);

      setUploadStatus("success");
      setTimeout(() => {
        router.push("/conversations");
      }, 1500);
    } catch (err: unknown) {
      setUploadStatus("error");
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to process conversation audio upload.");
      }
    }
  };

  if (authLoading) {
    return <div className="p-8 text-center text-sm text-muted-foreground">Loading...</div>;
  }

  if (!user) {
    return (
      <div className="text-center py-12 space-y-4">
        <p className="text-sm text-muted-foreground">Please sign in to record or upload audio.</p>
        <Button asChild>
          <Link href="/login">Sign In</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild className="gap-1.5 -ml-2">
          <Link href="/conversations">
            <ArrowLeft className="h-4 w-4" />
            Back to conversations
          </Link>
        </Button>
      </div>

      <Card className="shadow-md border-muted">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold">
                <Mic className="h-5 w-5" />
              </div>
              <div>
                <CardTitle className="text-xl">Upload Conversation Audio</CardTitle>
                <CardDescription>
                  Intake raw business audio for transcription and commitment tracking.
                </CardDescription>
              </div>
            </div>
            {activeWorkspace && (
              <Badge variant="outline" className="text-xs">
                {activeWorkspace.name}
              </Badge>
            )}
          </div>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-6">
            {error && (
              <div
                role="alert"
                className="p-3 text-xs rounded-lg bg-destructive/10 text-destructive flex items-center gap-2 border border-destructive/20"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {uploadStatus === "success" && (
              <div
                role="status"
                className="p-3 text-xs rounded-lg bg-emerald-500/10 text-emerald-600 flex items-center gap-2 border border-emerald-500/20"
              >
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>Audio successfully uploaded! Redirecting to conversations...</span>
              </div>
            )}

            {/* Title & Type */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Conversation Title</Label>
                <Input
                  id="title"
                  placeholder="e.g. Weekly Strategy Sync with Co-Founder"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={uploadStatus === "creating" || uploadStatus === "uploading"}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="type">Conversation Type</Label>
                <select
                  id="type"
                  value={conversationType}
                  onChange={(e) => setConversationType(e.target.value)}
                  disabled={uploadStatus === "creating" || uploadStatus === "uploading"}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <option value="voice_note">Voice Note (Founder Monologue / Reflection)</option>
                  <option value="meeting">Team Meeting / Strategy Call</option>
                  <option value="client_update">Client Review / Delivery Update</option>
                  <option value="board_sync">Investor / Advisory Sync</option>
                </select>
              </div>
            </div>

            {/* Audio Dropzone */}
            <div className="space-y-2">
              <Label>Audio Recording File</Label>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                  dragOver
                    ? "border-primary bg-primary/5"
                    : selectedFile
                    ? "border-emerald-500/50 bg-emerald-50/50 dark:bg-emerald-950/20"
                    : "border-muted hover:border-primary/50 hover:bg-muted/30"
                }`}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".wav,.mp3,.ogg,.flac,.m4a,.webm"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFileSelect(e.target.files[0]);
                    }
                  }}
                />

                {selectedFile ? (
                  <div className="flex items-center justify-between p-2 rounded-lg bg-background border">
                    <div className="flex items-center gap-3 truncate">
                      <FileAudio className="h-8 w-8 text-primary shrink-0" />
                      <div className="text-left truncate">
                        <p className="text-sm font-medium truncate">{selectedFile.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFile(null);
                        if (fileInputRef.current) fileInputRef.current.value = "";
                      }}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="mx-auto h-10 w-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
                      <UploadCloud className="h-5 w-5" />
                    </div>
                    <div className="text-sm">
                      <span className="font-semibold text-primary">Click to select audio</span> or drag and drop
                    </div>
                    <p className="text-xs text-muted-foreground">
                      WAV, MP3, OGG, FLAC, M4A, WebM (up to 25MB)
                    </p>
                  </div>
                )}
              </div>
            </div>
          </CardContent>

          <div className="p-6 pt-0 flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              asChild
              disabled={uploadStatus === "uploading" || uploadStatus === "creating"}
            >
              <Link href="/conversations">Cancel</Link>
            </Button>
            <Button
              type="submit"
              disabled={
                !selectedFile ||
                !title.trim() ||
                uploadStatus === "uploading" ||
                uploadStatus === "creating" ||
                uploadStatus === "success"
              }
            >
              {uploadStatus === "creating" && "Initializing conversation..."}
              {uploadStatus === "uploading" && "Uploading audio file..."}
              {uploadStatus === "success" && "Uploaded!"}
              {(uploadStatus === "idle" || uploadStatus === "error") && "Upload Audio"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
