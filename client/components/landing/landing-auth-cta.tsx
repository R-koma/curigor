"use client";

import Link from "next/link";

import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";

export default function LandingAuthCta({
  size = "default",
}: {
  size?: "default" | "lg";
}) {
  const { data: session, isPending } = authClient.useSession();

  // pending 中は未ログイン表示に固定し、プリレンダー出力と一致させて hydration mismatch を防ぐ
  if (session && !isPending) {
    return (
      <Button asChild size={size} variant="brand">
        <Link href="/dashboard">ダッシュボードへ</Link>
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Button asChild size={size} variant="ghost">
        <Link href="/sign-in">ログイン</Link>
      </Button>
      <Button asChild size={size} variant="brand">
        <Link href="/sign-in">無料で始める</Link>
      </Button>
    </div>
  );
}
