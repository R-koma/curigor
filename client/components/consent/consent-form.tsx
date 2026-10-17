"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ApiError } from "@/lib/api";
import { authClient } from "@/lib/auth-client";
import { submitConsent } from "@/lib/consent";

const LOAD_ERROR =
  "同意の状態を読み込めませんでした。時間をおいて再読み込みしてください";

export function ConsentForm({ termsVersion }: { termsVersion: number | null }) {
  const router = useRouter();
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (termsVersion === null) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitConsent(termsVersion);
      router.replace("/dashboard");
    } catch (err) {
      setSubmitting(false);
      if (err instanceof ApiError && err.code === "terms_version_outdated") {
        setAgreed(false);
        setError("規約が更新されました。内容を確かめてから同意してください");
        router.refresh();
        return;
      }
      setError("同意を記録できませんでした。もう一度お試しください");
    }
  };

  const signOut = () =>
    authClient.signOut({
      fetchOptions: { onSuccess: () => router.push("/sign-in") },
    });

  return (
    <AuthCard subtitle="利用を始める前に確かめてください">
      <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed">
        <li>
          Curigor は AI
          と対話して学ぶサービスです。応答には誤りが含まれることがあります
        </li>
        <li>
          応答・文字起こし・読み上げのため、入力した内容・添付した画像・録音した音声を、米国などにある事業者（OpenAI
          など）へ送ります。送り先と各国の制度はプライバシーポリシーに書いています
        </li>
        <li>利用できるのは 18 歳以上の方です</li>
      </ul>
      <p className="text-sm">
        <Link
          href="/terms"
          target="_blank"
          className="text-brand-text underline underline-offset-4"
        >
          利用規約
        </Link>
        と
        <Link
          href="/privacy"
          target="_blank"
          className="text-brand-text underline underline-offset-4"
        >
          プライバシーポリシー
        </Link>
        を読んでください。
      </p>
      <label className="flex cursor-pointer items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(event) => setAgreed(event.target.checked)}
          className="mt-0.5 size-4 shrink-0 accent-brand pointer-coarse:size-5"
        />
        <span>
          18
          歳以上であり、利用規約とプライバシーポリシー（外国にある第三者への個人データの提供を含む）に同意します
        </span>
      </label>
      {(error ?? (termsVersion === null ? LOAD_ERROR : null)) && (
        <p role="alert" className="text-sm text-destructive">
          {error ?? LOAD_ERROR}
        </p>
      )}
      <Button
        variant="brand"
        onClick={() => void handleSubmit()}
        disabled={!agreed || submitting || termsVersion === null}
        className="w-full"
      >
        {submitting && <Spinner size="sm" />}
        同意して始める
      </Button>
      <button
        type="button"
        onClick={() => void signOut()}
        className="cursor-pointer text-center text-xs text-muted-foreground hover:text-foreground"
      >
        同意せずにログアウト
      </button>
    </AuthCard>
  );
}
