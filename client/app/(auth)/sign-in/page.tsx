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

const signInSchema = z.object({
  email: z.email({ error: "有効なメールアドレスを入力してください。" }),
  password: z
    .string()
    .min(8, { error: "パスワードは8文字以上で入力してください。" }),
});

type SignInValues = z.infer<typeof signInSchema>;

export default function SignInPage() {
  const router = useRouter();
  const hydrated = useHydrated();
  const [isLoading, setIsLoading] = useState(false);
  const [serverError, setServerError] = useState("");

  const form = useForm<SignInValues>({
    resolver: zodResolver(signInSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const handleSignIn = async (values: SignInValues) => {
    setIsLoading(true);
    setServerError("");

    await authClient.signIn.email(
      { email: values.email, password: values.password, rememberMe: false },
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
    <Card className="w-full max-w-sm mx-auto shadow-xl border border-white/60 bg-white/80 backdrop-blur-sm dark:bg-slate-900/80 dark:border-slate-700/60">
      <CardHeader className="pb-2 pt-8 px-8 flex flex-col items-center gap-1">
        <span className="text-2xl font-bold tracking-tight text-indigo-600 dark:text-indigo-400">
          Curigor
        </span>
        <p className="text-sm text-muted-foreground">
          ログインして学習を続ける
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-5 px-8 pt-6">
        <GoogleLoginButton />
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-white/80 dark:bg-slate-900/80 px-2 text-muted-foreground">
              または
            </span>
          </div>
        </div>
        <form
          id="sign-in-form"
          method="post"
          onSubmit={form.handleSubmit(handleSignIn)}
        >
          <FieldGroup className="space-y-3">
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
                    className="h-11 text-base text-slate-700 dark:text-slate-300"
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
                    className="h-11 text-3xl tracking-[0.25em] placeholder:text-sm placeholder:tracking-normal text-slate-700 dark:text-slate-300"
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
          form="sign-in-form"
          disabled={!hydrated}
          isLoading={isLoading}
          className="bg-indigo-600 hover:bg-indigo-700 text-sm text-slate-100"
        >
          続ける
        </MorphingButton>
        <p className="text-center text-xs text-muted-foreground">
          アカウントをお持ちでない方は
          <Link
            href="/sign-up"
            className="text-indigo-600 dark:text-indigo-400 underline underline-offset-4 hover:opacity-80"
          >
            新規登録
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}
