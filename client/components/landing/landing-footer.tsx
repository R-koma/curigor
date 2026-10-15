import Link from "next/link";

import { OPERATOR } from "@/lib/legal";

export default function LandingFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row sm:px-6">
        <span className="font-bold tracking-tight text-brand-text">
          Curigor
        </span>
        <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
          <Link href="/sign-in" className="hover:text-foreground">
            ログイン
          </Link>
          <Link href="/sign-up" className="hover:text-foreground">
            新規登録
          </Link>
          {OPERATOR !== null && (
            <Link href="/privacy" className="hover:text-foreground">
              プライバシーポリシー
            </Link>
          )}
        </nav>
        <span className="text-sm text-muted-foreground">© 2026 Curigor</span>
      </div>
    </footer>
  );
}
