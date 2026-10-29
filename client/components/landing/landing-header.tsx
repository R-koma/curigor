import Link from "next/link";
import { AppLogo } from "@/components/brand/app-logo";
import { Badge } from "@/components/ui/badge";

import LandingAuthCta from "./landing-auth-cta";
import { RELEASE_STAGE } from "./landing-copy";

const sectionLinks = [
  { href: "#modes", label: "学び方" },
  { href: "#features", label: "できること" },
  { href: "#faq", label: "よくある質問" },
];

export default function LandingHeader() {
  return (
    <header className="sticky top-0 z-overlay border-b bg-background">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-6 px-4 sm:px-6">
        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-bold tracking-tight text-brand-text"
          >
            <AppLogo />
            Curigor
          </Link>
          <Badge variant="outline">{RELEASE_STAGE}</Badge>
        </div>
        <nav
          aria-label="ページ内"
          className="hidden flex-1 items-center gap-6 text-sm text-muted-foreground md:flex"
        >
          {sectionLinks.map(({ href, label }) => (
            <a key={href} href={href} className="hover:text-foreground">
              {label}
            </a>
          ))}
        </nav>
        <LandingAuthCta />
      </div>
    </header>
  );
}
