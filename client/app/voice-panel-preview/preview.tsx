"use client";

import { useState } from "react";
import { VoicePanel } from "@/components/chat/voice-panel";
import type {
  ConversationStatus,
  SpeechSpeed,
  TurnTimings,
} from "@/hooks/use-voice-conversation";
import type { TranscriptSegment } from "@/lib/stt/types";

interface Sample {
  title: string;
  status: ConversationStatus;
  segments: TranscriptSegment[];
  holdForReview?: boolean;
  timings?: TurnTimings;
}

const SAMPLES: Sample[] = [
  { title: "聞いている（空）", status: "listening", segments: [] },
  {
    title: "聞いている（文字起こし中）",
    status: "listening",
    segments: [
      { id: 1, text: "二分探索は、探す範囲を毎回半分に", status: "done" },
      { id: 2, text: "", status: "pending" },
    ],
  },
  {
    title: "区間の失敗",
    status: "listening",
    segments: [
      { id: 1, text: "二分探索は", status: "done" },
      { id: 2, text: "", status: "failed" },
      { id: 3, text: "半分に絞ります", status: "done" },
    ],
  },
  {
    title: "考え中（計測つき）",
    status: "thinking",
    segments: [],
    timings: { turnEnd: 0, sent: 820, firstToken: null, firstAudio: null },
  },
  {
    title: "話している",
    status: "speaking",
    segments: [],
    timings: { turnEnd: 0, sent: 820, firstToken: 2400, firstAudio: 3100 },
  },
  {
    title: "一時停止",
    status: "paused",
    segments: [{ id: 1, text: "途中まで話した内容", status: "done" }],
  },
  { title: "マイクの準備中", status: "starting", segments: [] },
  {
    title: "聞き取りカードの表示中",
    status: "listening",
    segments: [],
    holdForReview: true,
  },
];

export function VoicePanelPreview() {
  const [speed, setSpeed] = useState<SpeechSpeed>(1);
  return (
    <div className="mx-auto max-w-3xl space-y-8 px-6 py-10">
      {SAMPLES.map((sample) => (
        <div key={sample.title} className="space-y-2">
          <h2 className="text-sm font-semibold text-muted-foreground">
            {sample.title}
          </h2>
          <VoicePanel
            status={sample.status}
            segments={sample.segments}
            speed={speed}
            holdForReview={sample.holdForReview ?? false}
            timings={sample.timings ?? null}
            onSpeedChange={setSpeed}
            onPause={() => {}}
            onResume={() => {}}
            onSendNow={() => {}}
            onDiscard={() => {}}
            onEnd={() => {}}
          />
        </div>
      ))}
    </div>
  );
}
