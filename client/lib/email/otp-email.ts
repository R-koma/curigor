import { LOGO_PNG_BASE64 } from "@/lib/email/logo-png";
import type { EmailMessage } from "@/lib/email/send-email";

export const OTP_EXPIRES_IN_SECONDS = 300;
export const LOGO_CONTENT_ID = "curigor-logo";

const EXPIRES_MINUTES = OTP_EXPIRES_IN_SECONDS / 60;
const PREVIEW = `${EXPIRES_MINUTES} 分以内に入力してください`;
const INSTRUCTION = `次のコードを ${EXPIRES_MINUTES} 分以内に入力してください。`;
const DO_NOT_SHARE = "このコードを他人に伝えないでください。";
const NOT_YOU = "心当たりが無い場合は、このメールを無視してください。";
// メールクライアントは一覧のプレビューを本文の続きで埋めるので、空白で押し出してコードが出ないようにする
const PREVIEW_PADDING = "&nbsp;&zwnj;".repeat(100);

export function buildOtpEmail(to: string, otp: string): EmailMessage {
  const text = [otp, "", INSTRUCTION, "", DO_NOT_SHARE, NOT_YOU].join("\n");

  const html = `<!doctype html>
<html lang="ja">
  <body style="margin:0;padding:24px;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans','Noto Sans JP',sans-serif;color:#0f172a;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">${PREVIEW}${PREVIEW_PADDING}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;">
      <tr>
        <td style="padding:32px;">
          <p style="margin:0 0 8px;font-size:18px;font-weight:700;color:#155DFC;"><img src="cid:${LOGO_CONTENT_ID}" alt="" width="48" height="28" style="vertical-align:middle;margin-right:8px;border:0;">Curigor</p>
          <p style="margin:0 0 24px;font-size:14px;">${INSTRUCTION}</p>
          <p style="margin:0 0 24px;font-size:32px;font-weight:700;letter-spacing:8px;">${otp}</p>
          <p style="margin:0 0 8px;font-size:13px;color:#475569;">${DO_NOT_SHARE}</p>
          <p style="margin:0;font-size:13px;color:#475569;">${NOT_YOU}</p>
        </td>
      </tr>
    </table>
  </body>
</html>`;

  return {
    to,
    subject: "ログインコード",
    text,
    html,
    inlineImages: [
      {
        filename: "logo.png",
        contentId: LOGO_CONTENT_ID,
        content: Buffer.from(LOGO_PNG_BASE64, "base64"),
      },
    ],
  };
}
