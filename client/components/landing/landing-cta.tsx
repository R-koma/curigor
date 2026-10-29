import Link from "next/link";

import { AI_NOTICE } from "@/components/chat/ai-notice";
import { Button } from "@/components/ui/button";

export default function LandingCta() {
  return (
    <section className="bg-brand-bold">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-4 py-20 text-center sm:px-6">
        <h2 className="text-3xl font-bold tracking-tight text-brand-foreground">
          まず一つ、説明してみる。
        </h2>
        <p className="max-w-xl text-brand-foreground/80">
          アカウントを作ったら、すぐに最初のトピックを説明できます。
        </p>
        <Button
          asChild
          size="lg"
          className="bg-brand-foreground px-8 text-brand-deep hover:bg-brand-foreground/90 [a]:hover:bg-brand-foreground/90"
        >
          <Link href="/sign-up">はじめる</Link>
        </Button>
        <p className="text-xs text-brand-foreground/70">{AI_NOTICE}</p>
      </div>
    </section>
  );
}
