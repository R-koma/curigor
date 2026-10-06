"use client";

import { VoiceIntakePrompt } from "@/components/chat/voice-intake-prompt";
import { intakeSpeechText, type IntakeCard } from "@/lib/intake";

const LEAD =
  "Linux のカーネルを学ぶんですね。始める前に、少しだけ教えてください。答えにくいものはスキップして大丈夫です。";

const FULL: IntakeCard = {
  questions: [
    {
      key: "purpose",
      header: "目的",
      question: "今回、何ができるようになりたいですか？",
      options: [{ label: "基礎を理解したい", description: "" }],
      multi_select: false,
      preselected: [],
    },
    {
      key: "source",
      header: "教材",
      question: "何を使って学びますか？（複数選択可）",
      options: [{ label: "書籍", description: "" }],
      multi_select: true,
      preselected: [],
    },
    {
      key: "prior_knowledge",
      header: "今の理解",
      question: "このトピックについて、今どのくらい知っていますか？",
      options: [{ label: "初めて学ぶ", description: "" }],
      multi_select: false,
      preselected: [],
    },
  ],
};

const WITHOUT_PURPOSE: IntakeCard = { questions: FULL.questions.slice(1) };

const SAMPLES: { title: string; card: IntakeCard; disabled?: boolean }[] = [
  { title: "3 項目", card: FULL },
  { title: "目的を聞かない（API で目的が渡された）", card: WITHOUT_PURPOSE },
  { title: "送信中", card: FULL, disabled: true },
];

export function VoiceIntakePreview() {
  return (
    <div className="mx-auto max-w-3xl space-y-10 p-6">
      {SAMPLES.map(({ title, card, disabled }) => (
        <section key={title} className="space-y-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          <p className="text-base leading-relaxed">{LEAD}</p>
          <VoiceIntakePrompt
            card={card}
            disabled={disabled}
            onSkip={() => {}}
          />
          <pre className="whitespace-pre-wrap rounded-xl bg-muted p-3 text-xs text-muted-foreground">
            {intakeSpeechText(LEAD, card)}
          </pre>
        </section>
      ))}
    </div>
  );
}
