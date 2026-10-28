import { NextResponse } from "next/server";

import { auth } from "@/lib/auth";
import { deliverOtp } from "@/lib/auth-otp";
import { pool } from "@/lib/db";
import { verifyHuman } from "@/lib/human-check";
import { issueOtp } from "@/lib/otp-capture";
import { clientIp, requestOtp } from "@/lib/otp-request";
import { cancelOtpSend, reserveOtpSend } from "@/lib/otp-send-limit";

const STATUS_BY_CODE = {
  INVALID_EMAIL: 400,
  HUMAN_CHECK_FAILED: 400,
  OTP_SEND_LIMIT: 429,
  OTP_SEND_FAILED: 502,
} as const;

export async function POST(request: Request) {
  if (!request.headers.get("content-type")?.startsWith("application/json")) {
    return NextResponse.json({ code: "INVALID_REQUEST" }, { status: 415 });
  }
  let body: { email?: unknown; token?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ code: "INVALID_REQUEST" }, { status: 400 });
  }

  const ip = clientIp(request.headers);
  const result = await requestOtp(body?.email, ip, {
    verifyHuman: () => verifyHuman(body?.token, ip),
    reserve: (emailHash, ipHash) => reserveOtpSend(pool, emailHash, ipHash),
    cancel: (sendId) => cancelOtpSend(pool, sendId),
    issue: (email) =>
      issueOtp(() =>
        auth.api.sendVerificationOTP({ body: { email, type: "sign-in" } }),
      ),
    deliver: deliverOtp,
  });

  if (result.ok) return NextResponse.json({ success: true });
  return NextResponse.json(result.error, {
    status: STATUS_BY_CODE[result.error.code],
  });
}
