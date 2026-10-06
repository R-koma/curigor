import type { EmailMessage } from "@/lib/email/send-email";

export const OTP_EXPIRES_IN_SECONDS = 300;

const EXPIRES_TEXT = `${OTP_EXPIRES_IN_SECONDS / 60} 分間有効です`;
const DO_NOT_SHARE = "このコードを他人に伝えないでください。";
const NOT_YOU =
  "心当たりが無い場合は、このメールを無視してください。誰かが誤ってあなたのアドレスを入力した可能性があります。";

export function buildOtpEmail(to: string, otp: string): EmailMessage {
  const text = [
    otp,
    "",
    `Curigor のログインコードです。${EXPIRES_TEXT}。`,
    "",
    DO_NOT_SHARE,
    NOT_YOU,
  ].join("\n");

  const html = `<!doctype html>
<html lang="ja">
  <body style="margin:0;padding:24px;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans','Noto Sans JP',sans-serif;color:#0f172a;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;">
      <tr>
        <td style="padding:32px;">
          <p style="margin:0 0 8px;font-size:18px;font-weight:700;color:#2563eb;">Curigor</p>
          <p style="margin:0 0 24px;font-size:14px;">ログインコードです。${EXPIRES_TEXT}。</p>
          <p style="margin:0 0 24px;font-size:32px;font-weight:700;letter-spacing:8px;">${otp}</p>
          <p style="margin:0 0 8px;font-size:13px;color:#475569;">${DO_NOT_SHARE}</p>
          <p style="margin:0;font-size:13px;color:#475569;">${NOT_YOU}</p>
        </td>
      </tr>
    </table>
  </body>
</html>`;

  return { to, subject: "Curigor のログインコード", text, html };
}
