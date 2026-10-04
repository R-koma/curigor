"use client";

import { authClient } from "@/lib/auth-client";
import { useHydrated } from "@/hooks/use-hydrated";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import * as z from "zod";

import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Field, FieldError, FieldGroup } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

import GoogleLoginButton from "@/components/auth/google-login-button";
import { MorphingButton } from "@/components/auth/morphing-button";
import Link from "next/link";

const signUpSchema = z
  .object({
    name: z
      .string()
      .min(2, { message: "名前は2文字以上で入力してください。" })
      .max(50, { message: "名前は50文字以内で入力してください。" }),
    email: z.email({ error: "有効なメールアドレスを入力してください。" }),
    password: z
      .string()
      .min(8, { message: "パスワードは8文字以上で入力してください。" }),
    passwordConfirmation: z
      .string()
      .min(1, { message: "確認用パスワードを入力してください。" }),
  })
  .refine((data) => data.password === data.passwordConfirmation, {
    message: "パスワードが一致しません。",
    path: ["passwordConfirmation"],
  });

type SignUpValues = z.infer<typeof signUpSchema>;

export default function SignUpPage() {
  const router = useRouter();
  const hydrated = useHydrated();
  const [isLoading, setIsLoading] = useState(false);
  const [serverError, setServerError] = useState("");

  const form = useForm<SignUpValues>({
    resolver: zodResolver(signUpSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      passwordConfirmation: "",
    },
  });

  const handleSignUp = async (values: SignUpValues) => {
    setIsLoading(true);
    setServerError("");

    await authClient.signUp.email(
      { email: values.email, password: values.password, name: values.name },
      {
        onRequest: () => {
          setIsLoading(true);
        },
        onSuccess: () => {
          setIsLoading(false);
          router.push("/dashboard");
        },
        onError: (ctx) => {
          setIsLoading(false);
          setServerError(ctx.error.message);
        },
      },
    );
  };

  return (
    <Card className="w-full max-w-sm mx-auto shadow-xl border bg-card/80 backdrop-blur-sm">
      <CardHeader className="pb-2 pt-8 px-8 flex flex-col items-center gap-1">
        <span className="text-2xl font-bold tracking-tight text-brand-text">
          Curigor
        </span>
        <p className="text-sm text-muted-foreground">アカウントを作成する</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-5 px-8 pt-6">
        <GoogleLoginButton />
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card/80 px-2 text-muted-foreground">
              または
            </span>
          </div>
        </div>
        <form
          id="sign-up-form"
          method="post"
          onSubmit={form.handleSubmit(handleSignUp)}
        >
          <FieldGroup className="space-y-3">
            <Controller
              name="name"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid} className="w-full">
                  <Input
                    {...field}
                    id="name"
                    aria-invalid={fieldState.invalid}
                    placeholder="名前"
                    autoComplete="off"
                    className="h-11 text-base text-foreground"
                  />
                  {fieldState.invalid && (
                    <FieldError errors={[fieldState.error]} />
                  )}
                </Field>
              )}
            />
            <Controller
              name="email"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid} className="w-full">
                  <Input
                    {...field}
                    id="email"
                    aria-invalid={fieldState.invalid}
                    placeholder="メールアドレス"
                    autoComplete="off"
                    className="h-11 text-base text-foreground"
                  />
                  {fieldState.invalid && (
                    <FieldError errors={[fieldState.error]} />
                  )}
                </Field>
              )}
            />
            <Controller
              name="password"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid} className="w-full">
                  <Input
                    {...field}
                    type="password"
                    id="password"
                    aria-invalid={fieldState.invalid}
                    placeholder="パスワード"
                    autoComplete="off"
                    className="h-11 text-3xl tracking-[0.25em] placeholder:text-sm placeholder:tracking-normal text-foreground"
                  />
                  {fieldState.invalid && (
                    <FieldError errors={[fieldState.error]} />
                  )}
                </Field>
              )}
            />
            <Controller
              name="passwordConfirmation"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid} className="w-full">
                  <Input
                    {...field}
                    type="password"
                    id="passwordConfirmation"
                    aria-invalid={fieldState.invalid}
                    placeholder="確認用パスワード"
                    autoComplete="off"
                    className="h-11 text-3xl tracking-[0.25em] placeholder:text-sm placeholder:tracking-normal text-foreground"
                  />
                  {fieldState.invalid && (
                    <FieldError errors={[fieldState.error]} />
                  )}
                </Field>
              )}
            />
            {serverError && (
              <p className="text-sm text-destructive">{serverError}</p>
            )}
          </FieldGroup>
        </form>
      </CardContent>
      <CardFooter className="flex flex-col gap-4 px-8 pb-8">
        <MorphingButton
          type="submit"
          form="sign-up-form"
          disabled={!hydrated}
          isLoading={isLoading}
          className="bg-brand hover:bg-brand/90 text-sm text-brand-foreground"
        >
          続ける
        </MorphingButton>
        <p className="text-center text-xs text-muted-foreground">
          アカウントをお持ちの方は
          <Link
            href="/sign-in"
            className="text-brand-text underline underline-offset-4 hover:opacity-80"
          >
            ログイン
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}
