"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Calendar,
  FileAudio,
  Mic,
  Plus,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, Conversation } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function ConversationsPage() {
  const { user, activeWorkspace, loading: authLoading } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConversations = useCallback(async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.listConversations(activeWorkspace.id);
      setConversations(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load conversations.");
      }
    } finally {
      setLoading(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    if (activeWorkspace) {
      fetchConversations();
    } else if (!authLoading && !user) {
      setLoading(false);
    }
  }, [activeWorkspace, authLoading, user, fetchConversations]);

  if (authLoading || (loading && activeWorkspace)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3">
        <RefreshCw className="h-6 w-6 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Loading conversations...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center max-w-md mx-auto p-6">
        <div className="h-12 w-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mb-4">
          <Mic className="h-6 w-6" />
        </div>
        <h2 className="text-xl font-bold tracking-tight mb-2">Sign in to view conversations</h2>
        <p className="text-sm text-muted-foreground mb-6">
          Access your recorded meetings, voice notes, and extracted business commitments.
        </p>
        <div className="flex gap-3">
          <Button asChild>
            <Link href="/login">Sign In</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/register">Create Account</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Conversations & Audio
          </h1>
          <p className="text-sm text-muted-foreground">
            Evidence intake for voice notes, client calls, and team roadmaps.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchConversations}
            disabled={loading}
            className="gap-1.5"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button asChild className="gap-2">
            <Link href="/conversations/new">
              <Plus className="h-4 w-4" />
              New Conversation
            </Link>
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-destructive/10 text-destructive text-sm border border-destructive/20">
          {error}
        </div>
      )}

      {/* Conversations List */}
      {conversations.length === 0 ? (
        <Card className="border-dashed py-12 text-center">
          <CardHeader className="space-y-2">
            <div className="mx-auto h-12 w-12 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
              <Mic className="h-6 w-6" />
            </div>
            <CardTitle className="text-lg">No conversations recorded yet</CardTitle>
            <CardDescription className="max-w-sm mx-auto">
              Start by uploading an audio update or meeting recording to extract business commitments.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/conversations/new">
                <Plus className="h-4 w-4 mr-2" />
                Upload First Voice Update
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {conversations.map((conv) => (
            <Link
              key={conv.id}
              href={`/conversations/${conv.id}`}
              className="block group focus:outline-none"
              data-testid={`conversation-card-${conv.id}`}
            >
              <Card className="h-full group-hover:border-primary/60 group-hover:shadow-md transition-all flex flex-col justify-between cursor-pointer">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <Badge variant="outline" className="text-xs uppercase tracking-wider font-semibold">
                      {conv.conversation_type}
                    </Badge>
                    <Badge
                      variant={
                        conv.status === "uploaded" || conv.status === "completed"
                          ? "success"
                          : "secondary"
                      }
                      className="capitalize text-[11px]"
                    >
                      {conv.status}
                    </Badge>
                  </div>
                  <CardTitle className="text-base font-semibold line-clamp-2 mt-2 group-hover:text-primary transition-colors">
                    {conv.title}
                  </CardTitle>
                </CardHeader>

                <CardContent className="pt-0 space-y-3 text-xs text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-3.5 w-3.5 shrink-0" />
                    <span>
                      {new Date(conv.recorded_at || conv.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                  </div>

                  <div className="flex items-center justify-between border-t pt-3">
                    <div className="flex items-center gap-1.5 font-medium text-foreground">
                      <FileAudio className="h-3.5 w-3.5 text-primary" />
                      <span>{conv.audio_assets?.length || 0} Audio</span>
                    </div>
                    <div className="flex items-center gap-1.5 font-medium text-foreground">
                      <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                      <span>{conv.commitments_count || 0} Commitments</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

      )}
    </div>
  );
}
