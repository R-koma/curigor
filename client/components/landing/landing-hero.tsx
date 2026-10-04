import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function LandingHero() {
  return (
    <section className="bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-20 sm:px-6 md:py-28 lg:grid-cols-2">
        <div className="flex flex-col items-start gap-6">
          <Badge variant="info">プロテジェ効果 × AI</Badge>
          <h1 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            <span className="text-indigo-600 dark:text-indigo-400">
              「教える」
            </span>
            ことが、
            <br />
            最強の学習法。
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Curigor は AI に教えながら学ぶ学習アプリ。
            対話から自動でノートを生成し、AI フィードバックと
            忘却曲線に基づく復習スケジュールで、学んだ知識を長期記憶に定着させます。
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              asChild
              size="lg"
              className="bg-indigo-600 px-6 text-slate-100 hover:bg-indigo-700 [a]:hover:bg-indigo-700"
            >
              <Link href="/sign-up">無料で始める</Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="px-6">
              <Link href="/sign-in">ログイン</Link>
            </Button>
          </div>
        </div>
        <Card className="w-full max-w-md justify-self-center lg:justify-self-end">
          <CardContent className="flex flex-col gap-3">
            <div className="max-w-[85%] self-end rounded-lg bg-indigo-600 px-3 py-2 text-sm text-slate-100">
              二分探索は、ソート済み配列を半分ずつ絞り込んで探す方法です。だから計算量は
              O(log n) になります。
            </div>
            <div className="max-w-[85%] self-start rounded-lg bg-muted px-3 py-2 text-sm">
              いい説明ですね！では、配列がソートされていない場合はどうなりますか？
            </div>
            <div className="max-w-[85%] self-end rounded-lg bg-indigo-600 px-3 py-2 text-sm text-slate-100">
              えっと……そのままだと使えないので、先にソートが必要です。
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              AI に説明すると、理解の穴が見つかる。
            </p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
