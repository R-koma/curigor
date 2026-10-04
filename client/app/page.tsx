import type { Metadata } from "next";

import LandingCta from "@/components/landing/landing-cta";
import LandingFeatures from "@/components/landing/landing-features";
import LandingFooter from "@/components/landing/landing-footer";
import LandingHeader from "@/components/landing/landing-header";
import LandingHero from "@/components/landing/landing-hero";
import LandingHowItWorks from "@/components/landing/landing-how-it-works";

const description =
  "Curigor は「プロテジェ効果」を活用した AI 学習アプリ。AI に教えながら学び、ノート・フィードバック・忘却曲線に基づく復習スケジュールが自動生成されます。";

export const metadata: Metadata = {
  title: "Curigor | AI に教えて学ぶ学習アプリ",
  description,
  openGraph: {
    title: "Curigor",
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
        <LandingFeatures />
        <LandingHowItWorks />
        <LandingCta />
      </main>
      <LandingFooter />
    </>
  );
}
