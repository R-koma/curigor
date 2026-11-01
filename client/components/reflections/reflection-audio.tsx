"use client";

import { useEffect, useRef, useState } from "react";
import { PauseIcon, PlayIcon, SquareIcon, Volume2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { TooltipLabel } from "@/components/ui/tooltip";
import {
  SPEECH_FAILED_MESSAGE,
  useSpeechPlayback,
  type SpeechSource,
} from "@/hooks/use-speech-playback";
import { ApiError, fetchAPI } from "@/lib/api";
import type { ReflectionPeriod } from "@/lib/reflection";

export const REFLECTION_LIMIT_MESSAGE = "今日の振り返りの上限に達しました";

const REFLECTION_SOURCE: SpeechSource = { kind: "reflection" };

type Status = "idle" | "preparing" | "paused";

interface AudioState {
  key: string;
  status: Status;
  error: string | null;
}

function scriptErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 429) {
    return REFLECTION_LIMIT_MESSAGE;
  }
  return SPEECH_FAILED_MESSAGE;
}

interface ReflectionAudioProps {
  period: ReflectionPeriod;
  start: string;
}

export function ReflectionAudio({ period, start }: ReflectionAudioProps) {
  const { unlock, playAll, stop, hold, release, isSpeaking, error } =
    useSpeechPlayback({ source: REFLECTION_SOURCE });
  const key = `reflection:${period}:${start}`;
  const [state, setState] = useState<AudioState>({
    key,
    status: "idle",
    error: null,
  });
  const requestRef = useRef(0);
  const current = state.key === key ? state : null;
  const status = current?.status ?? "idle";
  const message = current?.error ?? error;

  useEffect(
    () => () => {
      requestRef.current += 1;
      stop();
    },
    [key, stop],
  );

  const listen = async () => {
    unlock();
    const request = ++requestRef.current;
    setState({ key, status: "preparing", error: null });
    try {
      const { sentences } = await fetchAPI<{ sentences: string[] }>(
        `/api/reflections/${period}/${start}/script`,
        { method: "POST" },
      );
      if (requestRef.current !== request) return;
      playAll(key, sentences);
      setState({ key, status: "idle", error: null });
    } catch (err) {
      if (requestRef.current !== request) return;
      setState({ key, status: "idle", error: scriptErrorMessage(err) });
    }
  };

  const pause = () => {
    hold();
    setState({ key, status: "paused", error: null });
  };

  const resume = () => {
    setState({ key, status: "idle", error: null });
    release();
  };

  const end = () => {
    requestRef.current += 1;
    stop();
    setState({ key, status: "idle", error: null });
  };

  const paused = status === "paused" && !isSpeaking;

  return (
    <div className="flex flex-col items-start gap-1 md:items-end">
      {isSpeaking || paused ? (
        <div
          role="group"
          aria-label="音声の再生"
          className="flex h-8 items-center gap-1 rounded-lg border pr-1 pl-2.5"
        >
          <span className="mr-1 text-xs text-muted-foreground">
            {paused ? "一時停止中" : "再生中"}
          </span>
          <TooltipLabel label={paused ? "再開" : "一時停止"}>
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={paused ? "再開" : "一時停止"}
              onClick={paused ? resume : pause}
            >
              {paused ? <PlayIcon /> : <PauseIcon />}
            </Button>
          </TooltipLabel>
          <TooltipLabel label="停止">
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label="停止"
              onClick={end}
            >
              <SquareIcon />
            </Button>
          </TooltipLabel>
        </div>
      ) : (
        <Button
          variant="outline"
          size="sm"
          disabled={status === "preparing"}
          aria-busy={status === "preparing"}
          onClick={() => void listen()}
        >
          {status === "preparing" ? (
            <Spinner size="sm" label="原稿を作成中" />
          ) : (
            <Volume2Icon aria-hidden />
          )}
          音声で聞く
        </Button>
      )}
      {message && (
        <p role="alert" className="text-xs text-muted-foreground">
          {message}
        </p>
      )}
    </div>
  );
}
