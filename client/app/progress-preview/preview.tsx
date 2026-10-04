"use client";

import { useState } from "react";
import { LearningProgressIndicator } from "@/components/chat/learning-progress";
import type { LearningProgress } from "@/hooks/use-chat-websocket";

const SAMPLES: { title: string; progress: LearningProgress }[] = [
  {
    title: "途中（前提あり・広げられる観点あり）",
    progress: {
      reached_aspects: ["値の埋め込み方"],
      target_count: 3,
      is_complete: false,
      intake: {
        purpose: "仕事で使うので、基礎をひと通り説明できるようになりたい",
        source: "入門書",
        prior_knowledge: "初めて学ぶ",
      },
      aspects: [
        { name: "値の埋め込み方", is_core: true, reached_stage: "reasoned" },
        { name: "値の指定と再利用", is_core: true, reached_stage: "defined" },
        { name: "エスケープの扱い", is_core: true, reached_stage: null },
        { name: "文字列の連結", is_core: false, reached_stage: "mentioned" },
        { name: "書式指定", is_core: false, reached_stage: null },
      ],
    },
  },
  {
    title: "前提の一部だけ・観点のみ",
    progress: {
      reached_aspects: [],
      target_count: 2,
      is_complete: false,
      intake: { purpose: "", source: "入門書", prior_knowledge: "" },
      aspects: [
        { name: "A", is_core: true, reached_stage: "applied" },
        { name: "B", is_core: true, reached_stage: null },
      ],
    },
  },
];

export function ProgressPreview() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="mx-auto max-w-3xl space-y-10 p-6">
      {SAMPLES.map(({ title, progress }, i) => (
        <section key={title} className="space-y-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          <LearningProgressIndicator
            progress={progress}
            open={open === i}
            onOpenChange={(o) => setOpen(o ? i : null)}
          />
        </section>
      ))}
    </div>
  );
}
