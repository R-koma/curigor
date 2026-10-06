"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import * as z from "zod";

import GoogleLoginButton from "@/components/auth/google-login-button";
import { MorphingButton } from "@/components/auth/morphing-button";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useHydrated } from "@/hooks/use-hydrated";

const emailSchema = z.object({
  email: z
    .string()
    .trim()
    .pipe(z.email({ error: "有効なメールアドレスを入力してください。" })),
});

type EmailValues = z.infer<typeof emailSchema>;

export interface EmailStepProps {
  defaultEmail: string;
  isSending: boolean;
  error: string;
  onSubmit: (email: string) => void;
  focusOnMount?: boolean;
}

export function EmailStep({
  defaultEmail,
  isSending,
  error,
  onSubmit,
  focusOnMount = false,
}: EmailStepProps) {
  const hydrated = useHydrated();
  const form = useForm<EmailValues>({
    resolver: zodResolver(emailSchema),
    defaultValues: { email: defaultEmail },
  });

  const { setFocus } = form;
  useEffect(() => {
    if (focusOnMount) setFocus("email");
  }, [focusOnMount, setFocus]);

  return (
    <>
      <GoogleLoginButton />
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="bg-card px-2 text-muted-foreground">または</span>
        </div>
      </div>
      <form
        id="sign-in-form"
        method="post"
        noValidate
        onSubmit={form.handleSubmit(({ email }) => onSubmit(email))}
        className="flex flex-col gap-5"
      >
        <FieldGroup className="space-y-3">
          <Controller
            name="email"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid} className="w-full">
                <FieldLabel htmlFor="email">メールアドレス</FieldLabel>
                <Input
                  {...field}
                  id="email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  aria-invalid={fieldState.invalid || Boolean(error)}
                  aria-describedby={
                    fieldState.invalid
                      ? "email-error"
                      : error
                        ? "email-send-error"
                        : undefined
                  }
                  className="h-11 text-base text-foreground"
                />
                {fieldState.invalid && (
                  <FieldError id="email-error" errors={[fieldState.error]} />
                )}
              </Field>
            )}
          />
          {error && <FieldError id="email-send-error">{error}</FieldError>}
        </FieldGroup>
        <MorphingButton
          type="submit"
          disabled={!hydrated}
          isLoading={isSending}
        >
          続ける
        </MorphingButton>
      </form>
    </>
  );
}
