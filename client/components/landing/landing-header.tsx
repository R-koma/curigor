import Link from "next/link";

import LandingAuthCta from "./landing-auth-cta";

export default function LandingHeader() {
  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link
          href="/"
          className="text-lg font-bold tracking-tight text-indigo-600 dark:text-indigo-400"
        >
          Curigor
        </Link>
        <LandingAuthCta />
      </div>
    </header>
  );
}
