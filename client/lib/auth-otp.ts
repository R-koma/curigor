import "server-only";

import type { EmailOTPOptions } from "better-auth/plugins";

import { DEV_FIXED_OTP_CODE, isDevFixedOtp } from "@/lib/dev-auth";
import { buildOtpEmail, OTP_EXPIRES_IN_SECONDS } from "@/lib/email/otp-email";
import { sendEmail } from "@/lib/email/send-email";

export async function deliverOtp(email: string, otp: string): Promise<void> {
  if (isDevFixedOtp(email)) {
    console.info(`[dev-auth] ${email} は開発用の固定コードを使います`);
    return;
  }
  if (process.env.NODE_ENV !== "production" && !process.env.RESEND_API_KEY) {
    console.info(`[dev-auth] ${email} のコード: ${otp}`);
    return;
  }
  await sendEmail(buildOtpEmail(email, otp));
}

export const emailOtpOptions: EmailOTPOptions = {
  otpLength: 6,
  expiresIn: OTP_EXPIRES_IN_SECONDS,
  allowedAttempts: 3,
  storeOTP: "hashed",
  generateOTP: ({ email }) =>
    isDevFixedOtp(email) ? DEV_FIXED_OTP_CODE : undefined,
  sendVerificationOTP: ({ email, otp }) => deliverOtp(email, otp),
};
