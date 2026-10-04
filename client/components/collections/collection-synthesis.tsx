"use client";

import { useState } from "react";
import Link from "next/link";
import { SparklesIcon } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import { generateSynthesis, type Synthesis } from "@/lib/collections";

const MIN_NOTES = 2;
const MAX_NOTES = 30;

export function CollectionSynthesis({
  collectionId,
  noteCount,
  initial,
}: {
  collectionId: string;
  noteCount: number;
  initial: Synthesis | null;
}) {
  const [synthesis, setSynthesis] = useState(initial);
  const [isGenerating, setIsGenerating] = useState(false);
  const noteCountOk = noteCount >= MIN_NOTES && noteCount <= MAX_NOTES;
  const canGenerate = noteCountOk && !isGenerating;

  const generate = async () => {
    setIsGenerating(true);
    try {
      setSynthesis(await generateSynthesis(collectionId));
    } catch {
      toast.error("まとめを作成できませんでした。もう一度お試しください");
    } finally {
      setIsGenerating(false);
    }
  };

  const generateButton = (label: string) => (
    <Button onClick={generate} disabled={!canGenerate} className="gap-2">
      {isGenerating ? <Spinner /> : <SparklesIcon className="h-4 w-4" />}
      {label}
    </Button>
  );

  return (
    <section id="synthesis" className="scroll-mt-8 space-y-6">
      <h2 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
        まとめ
      </h2>

      {!synthesis && (
        <div className="space-y-3 rounded-xl border bg-card p-6">
          <p className="text-sm text-muted-foreground">
            {noteCount < MIN_NOTES
              ? "まとめは2件以上のノートから作れます"
              : noteCount > MAX_NOTES
                ? "まとめは30件以下のノートから作れます"
                : "入っているノートから、全体のまとめと、ノートどうしのつながりを作ります。"}
          </p>
          {generateButton("まとめを作る")}
          {isGenerating && (
            <p className="text-xs text-muted-foreground">
              まとめを作っています（30秒ほどかかります）
            </p>
          )}
        </div>
      )}

      {synthesis && (
        <>
          {synthesis.is_stale && (
            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-warning/40 bg-warning/5 p-4 text-sm">
              <span>
                元のノートが更新されています。作り直すと最新の内容で作り直します。
              </span>
              {generateButton("作り直す")}
            </div>
          )}

          <Markdown variant="article">{synthesis.content}</Markdown>

          {synthesis.connections.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-semibold">ノートどうしのつながり</h3>
                <Button asChild variant="outline" size="sm">
                  <Link href={`/collections/${collectionId}/synthesis`}>
                    つながりを説明する
                  </Link>
                </Button>
              </div>
              <ol className="space-y-3">
                {synthesis.connections.map((c) => (
                  <li key={c.id} className="rounded-lg border bg-card p-4">
                    <p className="font-medium">{c.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {c.question}
                    </p>
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer text-muted-foreground">
                        AI の説明を見る
                      </summary>
                      <p className="mt-2">{c.explanation}</p>
                    </details>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {synthesis.insights.length > 0 && (
            <div className="space-y-3">
              <h3 className="font-semibold">対話で補強した説明</h3>
              <ul className="space-y-3">
                {synthesis.insights.map((insight) => (
                  <li
                    key={insight.id}
                    className="rounded-lg border-l-4 border-primary/60 bg-card p-4"
                  >
                    <p className="text-sm font-medium">
                      {insight.connection_title}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm">
                      {insight.content}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {synthesis.contradictions.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-semibold">ノートどうしの食い違い</h3>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {synthesis.contradictions.map((c, i) => (
                  <li key={i}>{c.description}</li>
                ))}
              </ul>
            </div>
          )}

          {synthesis.gaps.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-semibold">まだ学んでいない領域</h3>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {synthesis.gaps.map((gap) => (
                  <li key={gap}>{gap}</li>
                ))}
              </ul>
            </div>
          )}

          {!synthesis.is_stale && <div>{generateButton("作り直す")}</div>}
        </>
      )}
    </section>
  );
}
