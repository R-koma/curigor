"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import { CodeStep } from "@/components/auth/code-step";
import { EmailStep } from "@/components/auth/email-step";
import { useCountdown } from "@/hooks/use-countdown";
import { authClient } from "@/lib/auth-client";
import { otpErrorMessage } from "@/lib/otp-error";

export const RESEND_INTERVAL_SECONDS = 60;

type Step = "email" | "code";
type Mode = "sign-in" | "sign-up";

const MODE_TEXT: Record<
  Mode,
  { subtitle: string; prompt: string; linkLabel: string; href: string }
> = {
  "sign-in": {
    subtitle: "ログインして学習を続ける",
    prompt: "アカウントをお持ちでない方は",
    linkLabel: "新規登録",
    href: "/sign-up",
  },
  "sign-up": {
    subtitle: "アカウントを作成する",
    prompt: "アカウントをお持ちの方は",
    linkLabel: "ログイン",
    href: "/sign-in",
  },
};

export function SignInForm({
  mode = "sign-in",
  showDevCodeHint,
}: {
  mode?: Mode;
  showDevCodeHint: boolean;
}) {
  const text = MODE_TEXT[mode];
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");
  const [cameBack, setCameBack] = useState(false);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const { remaining, restart } = useCountdown(RESEND_INTERVAL_SECONDS);
  const verifyingRef = useRef(false);

  const sendCode = async (target: string): Promise<boolean> => {
    setIsSending(true);
    setError("");
    let sendError: unknown;
    try {
      ({ error: sendError } = await authClient.emailOtp.sendVerificationOtp({
        email: target,
        type: "sign-in",
      }));
    } catch {
      sendError = {};
    } finally {
      setIsSending(false);
    }
    if (sendError) {
      setError(otpErrorMessage(sendError, "send"));
      return false;
    }
    setEmail(target);
    setCode("");
    restart();
    return true;
  };

  const handleEmailSubmit = async (target: string) => {
    if (!(await sendCode(target))) return;
    setStatus(`${target} に 6 桁のコードを送りました`);
    setStep("code");
  };

  const handleResend = async () => {
    if (await sendCode(email)) setStatus(`${email} にコードを再送しました`);
  };

  const handleComplete = async (otp: string) => {
    if (verifyingRef.current) return;
    verifyingRef.current = true;
    setIsVerifying(true);
    setError("");
    let verifyError: { code?: string } | null = null;
    try {
      ({ error: verifyError } = await authClient.signIn.emailOtp({
        email,
        otp,
      }));
    } catch {
      verifyError = {};
    } finally {
      verifyingRef.current = false;
      setIsVerifying(false);
    }
    if (verifyError) {
      setError(otpErrorMessage(verifyError, "verify"));
      if (verifyError.code === "INVALID_OTP") setCode("");
      return;
    }
    router.push("/dashboard");
  };

  const handleChangeEmail = () => {
    setStep("email");
    setCameBack(true);
    setError("");
    setStatus("");
    setCode("");
  };

  return (
    <AuthCard subtitle={text.subtitle}>
      {step === "email" ? (
        <>
          <EmailStep
            defaultEmail={email}
            isSending={isSending}
            error={error}
            onSubmit={handleEmailSubmit}
            focusOnMount={cameBack}
          />
          <p className="text-center text-xs text-muted-foreground">
            {text.prompt}
            <Link
              href={text.href}
              className="text-brand-text underline underline-offset-4 hover:opacity-80"
            >
              {text.linkLabel}
            </Link>
          </p>
        </>
      ) : (
        <CodeStep
          email={email}
          code={code}
          onCodeChange={setCode}
          onComplete={handleComplete}
          isVerifying={isVerifying}
          error={error}
          status={status}
          resendIn={remaining}
          isResending={isSending}
          onResend={handleResend}
          onChangeEmail={handleChangeEmail}
          showDevCodeHint={showDevCodeHint}
        />
      )}
    </AuthCard>
  );
}
