"use client";

import { REGEXP_ONLY_DIGITS } from "input-otp";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/field";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { TONE_CLASSES } from "@/lib/tone";
import { cn } from "@/lib/utils";

export const OTP_LENGTH = 6;

export interface CodeStepProps {
  email: string;
  code: string;
  onCodeChange: (code: string) => void;
  onComplete: (code: string) => void;
  isVerifying: boolean;
  error: string;
  status: string;
  resendIn: number;
  isResending: boolean;
  onResend: () => void;
  onChangeEmail: () => void;
  showDevCodeHint: boolean;
}

export function CodeStep({
  code,
  onCodeChange,
  onComplete,
  isVerifying,
  error,
  status,
  resendIn,
  isResending,
  onResend,
  onChangeEmail,
  showDevCodeHint,
}: CodeStepProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (error) inputRef.current?.focus();
  }, [error]);

  return (
    <div className="flex flex-col gap-5">
      <p role="status" aria-live="polite" className="text-sm text-foreground">
        {status}
      </p>
      <div className="flex flex-col gap-2">
        <Label htmlFor="otp">確認コード</Label>
        <InputOTP
          ref={inputRef}
          id="otp"
          maxLength={OTP_LENGTH}
          pattern={REGEXP_ONLY_DIGITS}
          pasteTransformer={(text) => text.replace(/\D/g, "")}
          value={code}
          onChange={onCodeChange}
          onComplete={onComplete}
          autoFocus
          inputMode="numeric"
          autoComplete="one-time-code"
          pushPasswordManagerStrategy="none"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? "otp-error" : undefined}
          containerClassName="justify-center"
        >
          <InputOTPGroup>
            {Array.from({ length: OTP_LENGTH }, (_, index) => (
              <InputOTPSlot
                key={index}
                index={index}
                className="size-11 text-lg"
              />
            ))}
          </InputOTPGroup>
        </InputOTP>
        {isVerifying && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner />
            確認しています
          </p>
        )}
        {error && <FieldError id="otp-error">{error}</FieldError>}
      </div>
      {showDevCodeHint && (
        <p
          className={cn(
            "rounded-md px-3 py-2 text-xs",
            TONE_CLASSES.warning.soft,
            TONE_CLASSES.warning.text,
          )}
        >
          開発用: @example.test のアドレスはコード 000000
        </p>
      )}
      <div className="flex flex-col items-center gap-1">
        <Button
          type="button"
          variant="link"
          onClick={onResend}
          disabled={resendIn > 0 || isResending}
        >
          {resendIn > 0 ? `コードを再送（${resendIn} 秒後）` : "コードを再送"}
        </Button>
        <Button type="button" variant="link" onClick={onChangeEmail}>
          メールアドレスを変更
        </Button>
      </div>
    </div>
  );
}
