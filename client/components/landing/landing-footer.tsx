import Link from "next/link";

export default function LandingFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row sm:px-6">
        <span className="font-bold tracking-tight text-brand-text">
          Curigor
        </span>
        <nav className="flex items-center gap-6 text-sm text-muted-foreground">
          <Link href="/sign-in" className="hover:text-foreground">
            ログイン
          </Link>
          <Link href="/sign-in" className="hover:text-foreground">
            新規登録
          </Link>
        </nav>
        <span className="text-sm text-muted-foreground">© 2026 Curigor</span>
      </div>
    </footer>
  );
}
