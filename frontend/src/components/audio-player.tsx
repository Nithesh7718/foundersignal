"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  FileAudio,
  Loader2,
  Pause,
  Play,
  RotateCcw,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, AudioAsset } from "@/lib/api";

interface AudioPlayerProps {
  workspaceId: string;
  conversationId: string;
  audioAsset: AudioAsset;
}

export function AudioPlayer({
  workspaceId,
  conversationId,
  audioAsset,
}: AudioPlayerProps) {
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState<number>(
    audioAsset.duration_seconds || 0
  );
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    let active = true;
    let url: string | null = null;

    async function loadAudio() {
      setLoading(true);
      setError(null);
      try {
        const blob = await api.getAudioBlob(
          workspaceId,
          conversationId,
          audioAsset.id
        );
        if (!active) return;
        url = URL.createObjectURL(blob);
        setAudioUrl(url);
      } catch (err: unknown) {
        if (!active) return;
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to load audio stream.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadAudio();

    return () => {
      active = false;
      if (url) {
        URL.revokeObjectURL(url);
      }
    };
  }, [workspaceId, conversationId, audioAsset.id]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
  };

  const handleTimeUpdate = () => {
    if (!audioRef.current) return;
    setCurrentTime(audioRef.current.currentTime);
  };

  const handleLoadedMetadata = () => {
    if (!audioRef.current) return;
    if (audioRef.current.duration && !isNaN(audioRef.current.duration)) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    setCurrentTime(time);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    audioRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const changeSpeed = () => {
    if (!audioRef.current) return;
    const rates = [1, 1.25, 1.5, 2];
    const nextIdx = (rates.indexOf(playbackRate) + 1) % rates.length;
    const nextRate = rates[nextIdx];
    audioRef.current.playbackRate = nextRate;
    setPlaybackRate(nextRate);
  };

  const restartAudio = () => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = 0;
    setCurrentTime(0);
  };

  const formatTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) return "0:00";
    const mins = Math.floor(secs / 60);
    const remSecs = Math.floor(secs % 60);
    return `${mins}:${remSecs < 10 ? "0" : ""}${remSecs}`;
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <Card className="border border-border/80 shadow-sm" data-testid="audio-player-card">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <FileAudio className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base font-semibold leading-tight line-clamp-1">
                {audioAsset.file_name}
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">
                {formatFileSize(audioAsset.file_size_bytes)} &bull; {audioAsset.mime_type}
              </p>
            </div>
          </div>
          <Badge variant="outline" className="text-xs self-start sm:self-center font-mono">
            {formatTime(currentTime)} / {formatTime(duration)}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {loading && (
          <div className="flex items-center justify-center p-6 space-x-2 text-muted-foreground text-sm">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span>Buffering audio stream...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {audioUrl && !loading && !error && (
          <>
            <audio
              ref={audioRef}
              src={audioUrl}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={() => setIsPlaying(false)}
              data-testid="audio-element"
            />

            {/* Custom Scrub Bar */}
            <div className="space-y-1">
              <input
                type="range"
                min="0"
                max={duration || 100}
                step="0.1"
                value={currentTime}
                onChange={handleSeek}
                className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
                aria-label="Audio scrubber"
                data-testid="audio-scrubber"
              />
              <div className="flex justify-between text-[11px] text-muted-foreground font-mono">
                <span>{formatTime(currentTime)}</span>
                <span>{formatTime(duration)}</span>
              </div>
            </div>

            {/* Playback Controls */}
            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  onClick={togglePlay}
                  className="gap-1.5 min-w-[90px]"
                  data-testid="audio-play-pause-btn"
                >
                  {isPlaying ? (
                    <>
                      <Pause className="h-4 w-4" />
                      Pause
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 fill-current" />
                      Play
                    </>
                  )}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={restartAudio}
                  title="Restart"
                  data-testid="audio-restart-btn"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </Button>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={changeSpeed}
                  className="font-mono text-xs px-2.5"
                  title="Playback speed"
                  data-testid="audio-speed-btn"
                >
                  {playbackRate}x
                </Button>

                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={toggleMute}
                  title={isMuted ? "Unmute" : "Mute"}
                  data-testid="audio-mute-btn"
                >
                  {isMuted ? (
                    <VolumeX className="h-4 w-4 text-destructive" />
                  ) : (
                    <Volume2 className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
