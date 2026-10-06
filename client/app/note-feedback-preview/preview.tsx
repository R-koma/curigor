"use client";

import { NoteFeedbackPanel } from "@/components/notes/note-feedback-panel";
import type { Feedback } from "@/lib/feedback";

const LEARNING: Feedback = {
  id: "f1",
  understanding_level: "low",
  strength: "・二分探索が整列済みの配列を前提にすることを説明できています",
  improvements:
    "・計算量を O(n) と答えていましたが、実際には毎回半分に絞るので O(log n) です\n・終了条件の書き方が曖昧でした",
  session_type: "learning",
  created_at: "2026-06-01T03:00:00Z",
};

const REVIEW_1: Feedback = {
  ...LEARNING,
  id: "f2",
  understanding_level: "medium",
  improvements: "・終了条件 left <= right の理由を説明できるようにする",
  session_type: "review",
  created_at: "2026-06-04T03:00:00Z",
};

const REVIEW_2: Feedback = {
  ...LEARNING,
  id: "f3",
  understanding_level: "high",
  strength:
    "・計算量が O(log n) になる理由を、範囲が半分になることから説明できています",
  improvements: "",
  session_type: "review",
  created_at: "2026-06-10T03:00:00Z",
};

const LONG_TEXT =
  "・二分探索の計算量を O(n) と答えていましたが、毎回探索範囲が半分になるので、要素数が 2 倍になっても比較は 1 回しか増えず O(log n) になります。配列の長さを変えた具体例で確かめてみましょう";

const SAMPLES: {
  title: string;
  feedbacks: Feedback[];
  justUpdated?: boolean;
}[] = [
  {
    title: "履歴あり（学習 → 復習 2 回）",
    feedbacks: [LEARNING, REVIEW_1, REVIEW_2],
  },
  { title: "学習直後（1 件）", feedbacks: [LEARNING] },
  {
    title: "復習直後（更新の知らせ）",
    feedbacks: [LEARNING, REVIEW_1],
    justUpdated: true,
  },
  {
    title: "改善点なし・セッション不明",
    feedbacks: [{ ...REVIEW_2, session_type: null }],
  },
  {
    title: "強みなし（一部だけある）",
    feedbacks: [{ ...LEARNING, strength: "" }],
  },
  {
    title: "長いテキスト",
    feedbacks: [{ ...LEARNING, improvements: `${LONG_TEXT}\n${LONG_TEXT}` }],
  },
  {
    title: "未知の理解度",
    feedbacks: [{ ...LEARNING, understanding_level: "unknown" }],
  },
  { title: "空", feedbacks: [] },
];

export function NoteFeedbackPreview() {
  return (
    <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 md:grid-cols-2 lg:grid-cols-3">
      {SAMPLES.map((sample) => (
        <section key={sample.title} className="w-full max-w-xs">
          <h2 className="mb-3 text-sm font-medium">{sample.title}</h2>
          <NoteFeedbackPanel
            noteId="preview"
            feedbacks={sample.feedbacks}
            justUpdated={sample.justUpdated}
          />
        </section>
      ))}
    </div>
  );
}
