import Link from "next/link";

import { Button } from "@/components/ui/button";

import { HERO_HEADLINE_PHRASES, PRICING_NOTE_PHRASES } from "./landing-copy";
import LandingDialogueExamples from "./landing-dialogue-examples";
import Phrases from "./phrases";

export default function LandingHero() {
  return (
    <section className="bg-brand-wash">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 md:py-24 lg:grid-cols-2">
        <div className="flex flex-col items-start gap-6">
          <h1 className="text-3xl leading-tight min-[360px]:text-4xl font-bold tracking-tight text-balance sm:text-5xl">
            <Phrases phrases={HERO_HEADLINE_PHRASES} />
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Curigor は、学んだことを AI に説明しながら学ぶアプリです。AI
            が問い返すので、説明に詰まったところが、次に学ぶところになります。
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button asChild size="lg" variant="brand" className="px-6">
              <Link href="/sign-up">はじめる</Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="px-6">
              <Link href="/sign-in">ログイン</Link>
            </Button>
          </div>
          <p className="-mt-2 text-sm text-muted-foreground">
            <Phrases phrases={PRICING_NOTE_PHRASES} />
          </p>
        </div>
        <LandingDialogueExamples />
      </div>
    </section>
  );
}
