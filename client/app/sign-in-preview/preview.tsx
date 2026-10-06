"use client";

import { AuthCard } from "@/components/auth/auth-card";
import { CodeStep, type CodeStepProps } from "@/components/auth/code-step";
import { EmailStep } from "@/components/auth/email-step";
import { buildOtpEmail } from "@/lib/email/otp-email";

const noop = () => {};

const CODE_BASE: CodeStepProps = {
  email: "taro@example.com",
  code: "",
  onCodeChange: noop,
  onComplete: noop,
  isVerifying: false,
  error: "",
  status: "taro@example.com に 6 桁のコードを送りました",
  resendIn: 52,
  isResending: false,
  onResend: noop,
  onChangeEmail: noop,
  showDevCodeHint: false,
};

const CODE_SAMPLES: Array<{ title: string; props: Partial<CodeStepProps> }> = [
  { title: "コード入力（再送の待ち）", props: {} },
  { title: "再送できる", props: { resendIn: 0, code: "4829" } },
  { title: "確認中", props: { code: "482913", isVerifying: true } },
  { title: "誤ったコード", props: { error: "コードが正しくありません" } },
  {
    title: "有効期限切れ",
    props: {
      code: "482913",
      resendIn: 0,
      error: "コードの有効期限が切れました。再送してください",
    },
  },
  {
    title: "試行回数の上限",
    props: {
      code: "111111",
      resendIn: 0,
      error: "試行回数の上限に達しました。コードを再送してください",
    },
  },
  {
    title: "開発用の案内",
    props: {
      email: "dev@example.test",
      status: "dev@example.test に 6 桁のコードを送りました",
      showDevCodeHint: true,
    },
  },
];

const EMAIL_SAMPLE = buildOtpEmail("taro@example.com", "482913");

function Sample({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-muted-foreground">{title}</h2>
      {children}
    </section>
  );
}

export function SignInPreview() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-10 bg-brand-wash px-4 py-10">
      <h1 className="text-xl font-bold">ログイン画面の見本</h1>
      <div className="grid gap-8 md:grid-cols-2">
        <Sample title="メールアドレスの入力">
          <AuthCard subtitle="ログインして学習を続ける">
            <EmailStep
              defaultEmail=""
              isSending={false}
              error=""
              onSubmit={noop}
            />
          </AuthCard>
        </Sample>
        <Sample title="メールアドレスの入力（新規登録）">
          <AuthCard subtitle="アカウントを作成する">
            <EmailStep
              defaultEmail=""
              isSending={false}
              error=""
              onSubmit={noop}
            />
          </AuthCard>
        </Sample>
        <Sample title="送信中">
          <AuthCard subtitle="ログインして学習を続ける">
            <EmailStep
              defaultEmail="taro@example.com"
              isSending
              error=""
              onSubmit={noop}
            />
          </AuthCard>
        </Sample>
        <Sample title="送信の失敗">
          <AuthCard subtitle="ログインして学習を続ける">
            <EmailStep
              defaultEmail="taro@example.com"
              isSending={false}
              error="メールを送れませんでした。時間をおいて再度お試しください"
              onSubmit={noop}
            />
          </AuthCard>
        </Sample>
        {CODE_SAMPLES.map(({ title, props }) => (
          <Sample key={title} title={title}>
            <AuthCard subtitle="ログインして学習を続ける">
              <CodeStep {...CODE_BASE} {...props} />
            </AuthCard>
          </Sample>
        ))}
      </div>
      <Sample title={`メール: ${EMAIL_SAMPLE.subject}`}>
        <iframe
          title="OTP のメールの見本"
          srcDoc={EMAIL_SAMPLE.html}
          className="h-[480px] w-full rounded-md border bg-white"
        />
        <pre className="rounded-md border bg-card p-4 text-xs whitespace-pre-wrap">
          {EMAIL_SAMPLE.text}
        </pre>
      </Sample>
    </main>
  );
}
