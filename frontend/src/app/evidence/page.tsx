"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertCircle,
  ExternalLink,
  FileAudio,
  FileText,
  Filter,
  FolderKanban,
  Mic,
  Network,
  RefreshCw,
  Search,
  ShieldCheck,
  User,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, EvidenceGraph, EvidenceGraphNode } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function EvidenceGraphPage() {
  const { user, activeWorkspace, loading: authLoading } = useAuth();

  const [graphData, setGraphData] = useState<EvidenceGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Selected Node for Detail Inspector Panel
  const [selectedNode, setSelectedNode] = useState<EvidenceGraphNode | null>(null);

  const fetchGraph = useCallback(async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    setError(null);

    try {
      const data = await api.getEvidenceGraph(activeWorkspace.id);
      setGraphData(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load evidence graph.");
    } finally {
      setLoading(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    if (activeWorkspace) {
      fetchGraph();
    } else if (!authLoading && !user) {
      setLoading(false);
    }
  }, [activeWorkspace, authLoading, user, fetchGraph]);

  // Filtered Nodes & Edges
  const filteredNodes = useMemo(() => {
    if (!graphData) return [];
    return graphData.nodes.filter((node) => {
      // Type filter
      if (typeFilter !== "all" && node.type !== typeFilter) {
        return false;
      }
      // Status filter (for commitments or projects or conversations)
      if (statusFilter !== "all") {
        const nodeStatus = node.metadata.status as string | undefined;
        if (nodeStatus && nodeStatus !== statusFilter) {
          return false;
        }
      }
      // Search query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesLabel = node.label.toLowerCase().includes(query);
        const matchesQuote =
          typeof node.metadata.source_quote === "string" &&
          node.metadata.source_quote.toLowerCase().includes(query);
        const matchesSpeaker =
          typeof node.metadata.speaker === "string" &&
          node.metadata.speaker.toLowerCase().includes(query);
        const matchesSnippet =
          typeof node.metadata.snippet === "string" &&
          node.metadata.snippet.toLowerCase().includes(query);
        return matchesLabel || matchesQuote || matchesSpeaker || matchesSnippet;
      }
      return true;
    });
  }, [graphData, typeFilter, statusFilter, searchQuery]);

  const visibleNodeIds = useMemo(() => {
    return new Set(filteredNodes.map((n) => n.id));
  }, [filteredNodes]);

  const filteredEdges = useMemo(() => {
    if (!graphData) return [];
    return graphData.edges.filter(
      (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
    );
  }, [graphData, visibleNodeIds]);

  // Compute 2D Positions for nodes for visual canvas
  const positionedNodes = useMemo(() => {
    // Group nodes by type in horizontal layers
    const layers: Record<string, EvidenceGraphNode[]> = {
      conversation: [],
      audio: [],
      transcript: [],
      commitment: [],
      project: [],
      speaker: [],
    };

    filteredNodes.forEach((node) => {
      if (layers[node.type]) {
        layers[node.type].push(node);
      } else {
        layers.conversation.push(node);
      }
    });

    // Column positions (X coordinates)
    const layerX: Record<string, number> = {
      project: 100,
      conversation: 320,
      audio: 540,
      transcript: 540,
      commitment: 760,
      speaker: 980,
    };

    const nodePositions: Record<string, { x: number; y: number; node: EvidenceGraphNode }> = {};

    Object.entries(layers).forEach(([type, nodesInLayer]) => {
      const x = layerX[type] || 500;
      const count = nodesInLayer.length;
      const spacing = 110;
      const startY = Math.max(80, 240 - ((count - 1) * spacing) / 2);

      nodesInLayer.forEach((node, idx) => {
        const actualX = x;
        let actualY = startY + idx * spacing;
        if (type === "audio") {
          actualY = startY + idx * spacing * 2;
        } else if (type === "transcript") {
          actualY = startY + (idx * 2 + 1) * spacing;
        }
        nodePositions[node.id] = { x: actualX, y: actualY, node };
      });
    });

    return nodePositions;
  }, [filteredNodes]);

  // Node styling helpers
  const getNodeColor = (type: string) => {
    switch (type) {
      case "conversation":
        return { bg: "bg-blue-500/10 border-blue-500/40 text-blue-600 dark:text-blue-400", fill: "#3b82f6" };
      case "audio":
        return { bg: "bg-purple-500/10 border-purple-500/40 text-purple-600 dark:text-purple-400", fill: "#a855f7" };
      case "transcript":
        return { bg: "bg-emerald-500/10 border-emerald-500/40 text-emerald-600 dark:text-emerald-400", fill: "#10b981" };
      case "commitment":
        return { bg: "bg-amber-500/10 border-amber-500/40 text-amber-600 dark:text-amber-400", fill: "#f59e0b" };
      case "project":
        return { bg: "bg-indigo-500/10 border-indigo-500/40 text-indigo-600 dark:text-indigo-400", fill: "#6366f1" };
      case "speaker":
        return { bg: "bg-rose-500/10 border-rose-500/40 text-rose-600 dark:text-rose-400", fill: "#f43f5e" };
      default:
        return { bg: "bg-muted border-border text-foreground", fill: "#64748b" };
    }
  };

  const getNodeIcon = (type: string) => {
    switch (type) {
      case "conversation":
        return <Mic className="h-4 w-4" />;
      case "audio":
        return <FileAudio className="h-4 w-4" />;
      case "transcript":
        return <FileText className="h-4 w-4" />;
      case "commitment":
        return <ShieldCheck className="h-4 w-4" />;
      case "project":
        return <FolderKanban className="h-4 w-4" />;
      case "speaker":
        return <User className="h-4 w-4" />;
      default:
        return <Activity className="h-4 w-4" />;
    }
  };

  if (authLoading || (loading && !graphData)) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <RefreshCw className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm font-medium">Assembling workspace evidence graph...</p>
        </div>
      </div>
    );
  }

  if (!user || !activeWorkspace) {
    return (
      <div className="max-w-md mx-auto py-12 text-center space-y-4">
        <Network className="h-12 w-12 text-primary mx-auto" />
        <h2 className="text-xl font-bold">Authentication Required</h2>
        <p className="text-sm text-muted-foreground">
          Sign in to explore your workspace evidence relationships, commitments, and audio provenance.
        </p>
        <Button asChild>
          <Link href="/login">Sign In</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-16" data-testid="evidence-graph-page">
      {/* Page Title & KPI Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <Network className="h-6 w-6 text-primary" />
            Interactive Evidence Graph
          </h1>
          <p className="text-sm text-muted-foreground">
            Cryptographically linked provenance from spoken voice notes to extracted commitments, speakers, and projects.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchGraph()}
            disabled={loading}
            className="gap-2"
            data-testid="evidence-refresh-btn"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Sync Graph
          </Button>
        </div>
      </div>

      {/* Metrics Summary Strip */}
      {graphData && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="graph-metrics-strip">
          <div className="p-3 rounded-xl border bg-card/60 shadow-2xs space-y-0.5">
            <span className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">
              Conversations
            </span>
            <div className="text-xl font-bold text-foreground">{graphData.total_conversations}</div>
          </div>
          <div className="p-3 rounded-xl border bg-card/60 shadow-2xs space-y-0.5">
            <span className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">
              Audio Files
            </span>
            <div className="text-xl font-bold text-foreground">{graphData.total_audio_assets}</div>
          </div>
          <div className="p-3 rounded-xl border bg-card/60 shadow-2xs space-y-0.5">
            <span className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">
              Transcripts
            </span>
            <div className="text-xl font-bold text-foreground">{graphData.total_transcripts}</div>
          </div>
          <div className="p-3 rounded-xl border bg-card/60 shadow-2xs space-y-0.5">
            <span className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">
              Commitments
            </span>
            <div className="text-xl font-bold text-foreground">{graphData.total_commitments}</div>
          </div>
          <div className="p-3 rounded-xl border bg-card/60 shadow-2xs space-y-0.5 col-span-2 sm:col-span-1">
            <span className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">
              Projects
            </span>
            <div className="text-xl font-bold text-foreground">{graphData.total_projects}</div>
          </div>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <div
          role="alert"
          className="p-3 text-sm rounded-lg bg-destructive/10 text-destructive flex items-center gap-2 border border-destructive/20"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Filter and Search Controls */}
      <div className="p-4 rounded-xl border bg-card space-y-3 shadow-xs">
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search evidence by title, verbatim quote, speaker, or keyword..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 text-sm"
              data-testid="evidence-search-input"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-2.5 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            {/* Type Filter */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="flex h-10 w-full sm:w-44 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              data-testid="evidence-type-filter"
            >
              <option value="all">All Node Types</option>
              <option value="conversation">Conversations</option>
              <option value="audio">Audio Evidence</option>
              <option value="transcript">Transcripts</option>
              <option value="commitment">Commitments</option>
              <option value="project">Projects</option>
              <option value="speaker">Speakers</option>
            </select>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="flex h-10 w-full sm:w-40 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              data-testid="evidence-status-filter"
            >
              <option value="all">All Statuses</option>
              <option value="inferred">Inferred</option>
              <option value="confirmed">Confirmed</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
            </select>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-3 pt-1 text-xs text-muted-foreground border-t">
          <span className="font-semibold text-foreground">Legend:</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-indigo-500"></span> Projects</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-blue-500"></span> Conversations</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-purple-500"></span> Audio Files</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500"></span> Transcripts</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber-500"></span> Commitments</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-rose-500"></span> Speakers</span>
        </div>
      </div>

      {/* Main Canvas + Detail Drawer Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Interactive Visual Graph Canvas */}
        <div
          className={`${
            selectedNode ? "lg:col-span-3" : "lg:col-span-4"
          } transition-all duration-300`}
        >
          <div
            className="border rounded-2xl bg-card/60 p-4 sm:p-6 min-h-[520px] relative overflow-x-auto shadow-xs"
            data-testid="evidence-canvas-container"
          >
            {graphData && graphData.nodes.length === 0 ? (
              /* Empty State */
              <div
                className="flex flex-col items-center justify-center py-20 text-center space-y-4"
                data-testid="evidence-empty-state"
              >
                <div className="h-16 w-16 rounded-full bg-primary/10 text-primary flex items-center justify-center">
                  <Network className="h-8 w-8" />
                </div>
                <div className="space-y-1 max-w-sm">
                  <h3 className="text-lg font-bold text-foreground">No Evidence Signals Yet</h3>
                  <p className="text-sm text-muted-foreground">
                    Record your first audio voice note or upload a meeting conversation to generate an interactive evidence graph.
                  </p>
                </div>
                <div className="flex items-center gap-3 pt-2">
                  <Button asChild>
                    <Link href="/conversations/new">Intake Voice Note</Link>
                  </Button>
                </div>
              </div>
            ) : filteredNodes.length === 0 ? (
              /* No search matches */
              <div className="flex flex-col items-center justify-center py-20 text-center space-y-3">
                <Filter className="h-8 w-8 text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">No evidence matches your filters</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearchQuery("");
                    setTypeFilter("all");
                    setStatusFilter("all");
                  }}
                >
                  Reset Filters
                </Button>
              </div>
            ) : (
              /* SVG Connectors & Interactive Nodes */
              <div className="relative min-w-[1050px] min-h-[500px]">
                {/* SVG Connecting Edges */}
                <svg
                  className="absolute inset-0 w-full h-full pointer-events-none"
                  style={{ minWidth: "1050px", minHeight: "500px" }}
                >
                  <defs>
                    <marker
                      id="arrow"
                      viewBox="0 0 10 10"
                      refX="10"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 1 L 10 5 L 0 9 z" fill="#94a3b8" />
                    </marker>
                  </defs>

                  {filteredEdges.map((edge) => {
                    const sourcePos = positionedNodes[edge.source];
                    const targetPos = positionedNodes[edge.target];
                    if (!sourcePos || !targetPos) return null;

                    const sx = sourcePos.x + 90;
                    const sy = sourcePos.y + 25;
                    const tx = targetPos.x;
                    const ty = targetPos.y + 25;

                    const isHighlighted =
                      selectedNode?.id === edge.source || selectedNode?.id === edge.target;

                    return (
                      <g key={edge.id}>
                        <path
                          d={`M ${sx} ${sy} C ${(sx + tx) / 2} ${sy}, ${(sx + tx) / 2} ${ty}, ${tx} ${ty}`}
                          fill="none"
                          stroke={isHighlighted ? "#3b82f6" : "#cbd5e1"}
                          strokeWidth={isHighlighted ? "2.5" : "1.5"}
                          strokeDasharray={edge.type === "spoken_by" ? "4,4" : "none"}
                          className="dark:stroke-slate-700 transition-colors"
                          markerEnd="url(#arrow)"
                        />
                      </g>
                    );
                  })}
                </svg>

                {/* Nodes positioned in canvas */}
                {filteredNodes.map((node) => {
                  const pos = positionedNodes[node.id];
                  if (!pos) return null;

                  const color = getNodeColor(node.type);
                  const isSelected = selectedNode?.id === node.id;

                  return (
                    <div
                      key={node.id}
                      style={{
                        position: "absolute",
                        left: `${pos.x}px`,
                        top: `${pos.y}px`,
                        width: "180px",
                      }}
                      onClick={() => setSelectedNode(node)}
                      className={`cursor-pointer rounded-xl border p-2.5 transition-all duration-200 select-none shadow-xs hover:shadow-md hover:scale-102 ${
                        color.bg
                      } ${
                        isSelected
                          ? "ring-2 ring-primary ring-offset-2 ring-offset-background scale-105 z-20"
                          : "bg-card hover:bg-card/90 z-10"
                      }`}
                      data-testid={`graph-node-${node.id}`}
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="h-7 w-7 rounded-lg flex items-center justify-center shrink-0 border"
                          style={{ borderColor: color.fill, color: color.fill }}
                        >
                          {getNodeIcon(node.type)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block truncate">
                            {node.type}
                          </span>
                          <p className="text-xs font-bold text-foreground truncate leading-tight">
                            {node.label}
                          </p>
                        </div>
                      </div>

                      {/* Micro Badge for status or confidence */}
                      <div className="mt-2 flex items-center justify-between text-[10px]">
                        {Boolean(node.metadata.status) && (
                          <span className="capitalize font-medium text-muted-foreground truncate">
                            {String(node.metadata.status).replace("_", " ")}
                          </span>
                        )}
                        {Boolean(node.metadata.confidence_score) && (
                          <span className="font-semibold text-emerald-600 font-mono">
                            {Math.round(Number(node.metadata.confidence_score) * 100)}%
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Evidence Detail Inspector Panel */}
        {selectedNode && (
          <div className="lg:col-span-1">
            <Card
              className="sticky top-6 shadow-md border-primary/20 animate-in fade-in slide-in-from-right-2 duration-200"
              data-testid="node-detail-panel"
            >
              <CardHeader className="pb-3 border-b">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className="h-8 w-8 rounded-lg flex items-center justify-center border"
                      style={{
                        borderColor: getNodeColor(selectedNode.type).fill,
                        color: getNodeColor(selectedNode.type).fill,
                      }}
                    >
                      {getNodeIcon(selectedNode.type)}
                    </div>
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                        {selectedNode.type} Node
                      </span>
                      <CardTitle className="text-sm font-bold truncate max-w-[170px]">
                        {selectedNode.label}
                      </CardTitle>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => setSelectedNode(null)}
                    aria-label="Close detail panel"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="pt-4 space-y-4 text-xs">
                {/* Specific detail by node type */}
                {selectedNode.type === "commitment" && (
                  <div className="space-y-3">
                    <div>
                      <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                        Status
                      </span>
                      <div className="mt-1">
                        <Badge
                          variant={
                            selectedNode.metadata.status === "completed"
                              ? "success"
                              : selectedNode.metadata.status === "confirmed"
                              ? "default"
                              : selectedNode.metadata.status === "inferred"
                              ? "warning"
                              : "secondary"
                          }
                          className="capitalize"
                        >
                          {String(selectedNode.metadata.status).replace("_", " ")}
                        </Badge>
                      </div>
                    </div>

                    {Boolean(selectedNode.metadata.confidence_score) && (
                      <div>
                        <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                          Extraction Confidence
                        </span>
                        <p className="font-mono text-emerald-600 font-bold mt-0.5">
                          {Math.round(Number(selectedNode.metadata.confidence_score) * 100)}% Verified
                        </p>
                      </div>
                    )}

                    {Boolean(selectedNode.metadata.speaker) && (
                      <div>
                        <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                          Speaker
                        </span>
                        <p className="text-foreground font-medium mt-0.5">
                          {String(selectedNode.metadata.speaker)}
                        </p>
                      </div>
                    )}

                    <div>
                      <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                        Source Quotation
                      </span>
                      <div className="p-2.5 rounded-lg bg-muted/40 border italic text-muted-foreground mt-1 text-[11px] leading-relaxed">
                        “{String(selectedNode.metadata.source_quote || "No quotation captured.")}”
                      </div>
                    </div>

                    {Boolean(selectedNode.metadata.conversation_id) && (
                      <Button asChild size="sm" className="w-full gap-1.5 mt-2">
                        <Link
                          href={`/conversations/${selectedNode.metadata.conversation_id}`}
                          data-testid="view-source-conversation-btn"
                        >
                          <span>Open Conversation</span>
                          <ExternalLink className="h-3.5 w-3.5" />
                        </Link>
                      </Button>
                    )}
                  </div>
                )}

                {selectedNode.type === "conversation" && (
                  <div className="space-y-3">
                    <div>
                      <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                        Conversation Type
                      </span>
                      <p className="font-medium text-foreground capitalize mt-0.5">
                        {String(selectedNode.metadata.conversation_type).replace("_", " ")}
                      </p>
                    </div>

                    {Boolean(selectedNode.metadata.recorded_at) && (
                      <div>
                        <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                          Recorded At
                        </span>
                        <p className="text-muted-foreground mt-0.5">
                          {new Date(String(selectedNode.metadata.recorded_at)).toLocaleString()}
                        </p>
                      </div>
                    )}

                    <Button asChild size="sm" className="w-full gap-1.5 mt-2">
                      <Link
                        href={`/conversations/${selectedNode.metadata.id}`}
                        data-testid="open-conversation-node-btn"
                      >
                        <span>View Full Conversation</span>
                        <ExternalLink className="h-3.5 w-3.5" />
                      </Link>
                    </Button>
                  </div>
                )}

                {selectedNode.type === "transcript" && (
                  <div className="space-y-3">
                    <div>
                      <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                        Language
                      </span>
                      <p className="font-medium text-foreground uppercase mt-0.5">
                        {String(selectedNode.metadata.language || "en-IN")}
                      </p>
                    </div>

                    <div>
                      <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                        Transcript Snippet
                      </span>
                      <div className="p-2.5 rounded-lg bg-muted/40 border text-muted-foreground mt-1 text-[11px] leading-relaxed">
                        {String(selectedNode.metadata.snippet || "Transcript empty.")}
                      </div>
                    </div>

                    {Boolean(selectedNode.metadata.conversation_id) && (
                      <Button asChild size="sm" variant="outline" className="w-full gap-1.5 mt-2">
                        <Link href={`/conversations/${selectedNode.metadata.conversation_id}`}>
                          <span>View in Conversation</span>
                          <ExternalLink className="h-3.5 w-3.5" />
                        </Link>
                      </Button>
                    )}
                  </div>
                )}

                {selectedNode.type === "audio" && (
                  <div className="space-y-3">
                    <div>
                      <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                        Audio File Name
                      </span>
                      <p className="font-medium text-foreground truncate mt-0.5">
                        {String(selectedNode.metadata.file_name)}
                      </p>
                    </div>

                    <div>
                      <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                        MIME Content Type
                      </span>
                      <p className="font-mono text-muted-foreground mt-0.5">
                        {String(selectedNode.metadata.mime_type || "audio/wav")}
                      </p>
                    </div>

                    {Boolean(selectedNode.metadata.duration_seconds) && (
                      <div>
                        <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                          Duration
                        </span>
                        <p className="font-mono text-foreground mt-0.5">
                          {Number(selectedNode.metadata.duration_seconds).toFixed(1)} seconds
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {selectedNode.type === "project" && (
                  <div className="space-y-3">
                    <div>
                      <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                        Project Name
                      </span>
                      <p className="font-bold text-foreground mt-0.5">
                        {String(selectedNode.metadata.name)}
                      </p>
                    </div>

                    {Boolean(selectedNode.metadata.description) && (
                      <div>
                        <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                          Description
                        </span>
                        <p className="text-muted-foreground mt-0.5">
                          {String(selectedNode.metadata.description)}
                        </p>
                      </div>
                    )}

                    <Button asChild size="sm" className="w-full gap-1.5 mt-2">
                      <Link href="/projects" data-testid="open-project-node-btn">
                        <span>Go to Projects</span>
                        <ExternalLink className="h-3.5 w-3.5" />
                      </Link>
                    </Button>
                  </div>
                )}

                {selectedNode.type === "speaker" && (
                  <div className="space-y-3">
                    <div>
                      <span className="font-semibold text-muted-foreground uppercase text-[10px]">
                        Speaker Identity
                      </span>
                      <p className="font-bold text-foreground mt-0.5">
                        {String(selectedNode.metadata.name)}
                      </p>
                    </div>
                    <p className="text-muted-foreground text-[11px]">
                      Spoken promises by this individual are cryptographically tracked in the evidence graph.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
