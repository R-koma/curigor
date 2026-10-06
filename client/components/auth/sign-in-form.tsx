"use client";

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

export function SignInForm({ showDevCodeHint }: { showDevCodeHint: boolean }) {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");
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
    setError("");
    setStatus("");
    setCode("");
  };

  return (
    <AuthCard>
      {step === "email" ? (
        <EmailStep
          defaultEmail={email}
          isSending={isSending}
          error={error}
          onSubmit={handleEmailSubmit}
        />
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
