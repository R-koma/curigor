import { CalendarClock, CircleCheck, CircleDashed } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

import { sampleNote } from "./landing-samples";
import Phrases from "./phrases";

const points = [
  {
    title: "ノート",
    description:
      "対話の内容を整理したノートができます。自分でまとめ直さなくても、あとから読み返せます。",
  },
  {
    title: "フィードバック",
    description: "説明できたこと・足りなかったことを、観点ごとに返します。",
  },
  {
    title: "復習",
    description:
      "忘れかけたころに、復習の日が来ます。もう一度説明して、覚えているかを確かめます。思い出そうとしたあとなら、ノートを見ることもできます。",
  },
];

function SampleNoteCard() {
  return (
    <Card className="w-full max-w-md justify-self-center lg:justify-self-start">
      <CardContent className="flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <p className="text-xs text-muted-foreground">ノートの例</p>
          <h3 className="text-lg font-semibold">{sampleNote.title}</h3>
        </div>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm leading-relaxed">
          {sampleNote.summary.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <div className="flex flex-col gap-2 border-t pt-4 text-sm">
          <p className="text-xs font-medium text-muted-foreground">
            説明できた観点
          </p>
          {sampleNote.explained.map((aspect) => (
            <p key={aspect} className="flex items-start gap-2">
              <CircleCheck
                aria-hidden
                className="mt-0.5 size-4 shrink-0 text-success-text"
              />
              {aspect}
            </p>
          ))}
          <p className="mt-2 text-xs font-medium text-muted-foreground">
            次に学ぶこと
          </p>
          {sampleNote.nextToLearn.map((aspect) => (
            <p key={aspect} className="flex items-start gap-2">
              <CircleDashed
                aria-hidden
                className="mt-0.5 size-4 shrink-0 text-warning-text"
              />
              {aspect}
            </p>
          ))}
        </div>
        <p className="flex items-center gap-2 border-t pt-4 text-sm text-muted-foreground">
          <CalendarClock aria-hidden className="size-4 shrink-0" />
          次の復習: {sampleNote.nextReview}
        </p>
      </CardContent>
    </Card>
  );
}

export default function LandingAfterSession() {
  return (
    <section id="features" className="scroll-mt-14 border-y bg-muted/30">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2">
        <div className="flex flex-col gap-8">
          <h2 className="text-3xl font-bold tracking-tight text-balance">
            <Phrases
              phrases={["終わったら、", "ノートと次の復習の日が", "できている"]}
            />
          </h2>
          <dl className="flex flex-col gap-6">
            {points.map(({ title, description }) => (
              <div key={title} className="flex flex-col gap-1">
                <dt className="font-semibold">{title}</dt>
                <dd className="text-sm leading-relaxed text-muted-foreground">
                  {description}
                </dd>
              </div>
            ))}
          </dl>
        </div>
        <SampleNoteCard />
      </div>
    </section>
  );
}
