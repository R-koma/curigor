export type OtpStage = "send" | "verify";

export interface AuthErrorLike {
  code?: string;
  status?: number;
  retryAfterSeconds?: number;
}

const MESSAGES_BY_CODE: Record<string, string> = {
  INVALID_OTP: "コードが正しくありません",
  OTP_EXPIRED: "コードの有効期限が切れました。再送してください",
  TOO_MANY_ATTEMPTS: "試行回数の上限に達しました。コードを再送してください",
  INVALID_EMAIL: "有効なメールアドレスを入力してください。",
  HUMAN_CHECK_FAILED:
    "自動送信でないことを確かめられませんでした。ページを読み込み直してお試しください",
};

function waitText(seconds: number): string {
  const minutes = Math.ceil(seconds / 60);
  return minutes < 60
    ? `約 ${minutes} 分`
    : `約 ${Math.ceil(minutes / 60)} 時間`;
}

export function otpErrorMessage(error: AuthErrorLike, stage: OtpStage): string {
  if (error.code === "OTP_SEND_LIMIT" && error.retryAfterSeconds) {
    return `コードを送れる回数の上限に達しました。${waitText(error.retryAfterSeconds)}後にもう一度お試しください`;
  }
  const byCode = error.code ? MESSAGES_BY_CODE[error.code] : undefined;
  if (byCode) return byCode;
  if (error.status === 429) return "しばらく待ってからお試しください";
  return stage === "send"
    ? "メールを送れませんでした。時間をおいて再度お試しください"
    : "ログインできませんでした。時間をおいて再度お試しください";
}
