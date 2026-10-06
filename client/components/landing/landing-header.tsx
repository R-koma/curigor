import Link from "next/link";
import { AppLogo } from "@/components/brand/app-logo";

import LandingAuthCta from "./landing-auth-cta";

export default function LandingHeader() {
  return (
    <header className="sticky top-0 z-overlay border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-lg font-bold tracking-tight text-brand-text"
        >
          <AppLogo />
          Curigor
        </Link>
        <LandingAuthCta />
      </div>
    </header>
  );
}
