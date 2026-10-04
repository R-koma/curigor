import {
  CalendarClock,
  ImageIcon,
  LineChart,
  MessagesSquare,
  NotebookPen,
  Sparkles,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

const features = [
  {
    icon: MessagesSquare,
    title: "AI との対話で学ぶ",
    description:
      "プロテジェ効果を応用。AI に説明することで、自分の理解の穴が見つかります。",
  },
  {
    icon: NotebookPen,
    title: "ノート自動生成",
    description:
      "対話の内容から学習ノートを自動生成。自分でまとめ直す手間はゼロ。",
  },
  {
    icon: Sparkles,
    title: "AI フィードバック",
    description:
      "理解度や説明の弱点を AI が分析し、次に学ぶべきポイントを提示します。",
  },
  {
    icon: CalendarClock,
    title: "忘却曲線ベースの復習",
    description:
      "忘却曲線に基づき、忘れかけた最適なタイミングで復習を提案します。",
  },
  {
    icon: ImageIcon,
    title: "画像添付対応",
    description:
      "図やスクリーンショットを添付して、そのまま質問・学習できます。",
  },
  {
    icon: LineChart,
    title: "学習の見える化",
    description:
      "ダッシュボードで学習の記録と復習の進捗をひと目で確認できます。",
  },
];

export default function LandingFeatures() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
      <h2 className="text-center text-3xl font-bold tracking-tight">
        学びを定着させる仕組み
      </h2>
      <p className="mx-auto mt-3 max-w-2xl text-center text-muted-foreground">
        「学ぶ → まとめる → 振り返る → 復習する」のサイクルを、AI
        がまるごと支えます。
      </p>
      <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {features.map(({ icon: Icon, title, description }) => (
          <Card key={title}>
            <CardContent className="flex flex-col gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-brand-soft">
                <Icon className="size-5 text-brand-text" />
              </div>
              <h3 className="font-semibold">{title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
