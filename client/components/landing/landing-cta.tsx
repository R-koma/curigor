import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function LandingCta() {
  return (
    <section className="bg-brand-bold">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-4 py-20 text-center sm:px-6">
        <h2 className="text-3xl font-bold tracking-tight text-brand-foreground">
          今日から「教えて学ぶ」を始めよう
        </h2>
        <p className="max-w-xl text-brand-foreground/80">
          無料でアカウントを作成して、すぐに学習を開始できます。
        </p>
        <Button
          asChild
          size="lg"
          className="bg-brand-foreground px-8 text-brand-deep hover:bg-brand-foreground/90 [a]:hover:bg-brand-foreground/90"
        >
          <Link href="/sign-up">無料で始める</Link>
        </Button>
      </div>
    </section>
  );
}
