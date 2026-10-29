import type { Metadata } from "next";

import LandingAfterSession from "@/components/landing/landing-after-session";
import LandingCta from "@/components/landing/landing-cta";
import LandingFaq from "@/components/landing/landing-faq";
import LandingFooter from "@/components/landing/landing-footer";
import LandingHeader from "@/components/landing/landing-header";
import LandingHero from "@/components/landing/landing-hero";
import LandingHowItWorks from "@/components/landing/landing-how-it-works";
import LandingModes from "@/components/landing/landing-modes";
import LandingMoreFeatures from "@/components/landing/landing-more-features";

const title = "Curigor | 説明して学ぶ AI 学習アプリ";
const description =
  "学んだことを AI に説明すると、問い返しで分かっていない所が見つかる。対話からノートとフィードバックを作り、忘れかけたころに復習を届ける学習アプリです。";

export const metadata: Metadata = {
  title,
  description,
  openGraph: {
    title,
    description,
    type: "website",
    url: "/",
    siteName: "Curigor",
  },
  twitter: {
    card: "summary_large_image",
  },
};

export default function Home() {
  return (
    <>
      <LandingHeader />
      <main>
        <LandingHero />
        <LandingModes />
        <LandingAfterSession />
        <LandingMoreFeatures />
        <LandingHowItWorks />
        <LandingFaq />
        <LandingCta />
      </main>
      <LandingFooter />
    </>
  );
}
