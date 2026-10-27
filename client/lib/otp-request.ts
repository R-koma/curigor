import "server-only";

import { createHmac } from "node:crypto";

import * as z from "zod";

import { isDevFixedOtp } from "@/lib/dev-auth";

export const OTP_SEND_LIMITS = {
  ipHourly: 10,
  emailHourly: 5,
  emailDaily: 10,
} as const;

export type OtpRequestError =
  | { code: "INVALID_EMAIL" }
  | { code: "OTP_SEND_LIMIT"; retryAfterSeconds: number }
  | { code: "OTP_SEND_FAILED" };

export type OtpRequestResult =
  { ok: true } | { ok: false; error: OtpRequestError };

export type Reservation = { sendId: string } | { retryAfterSeconds: number };

export interface OtpRequestDeps {
  reserve: (emailHash: string, ipHash: string | null) => Promise<Reservation>;
  cancel: (sendId: string) => Promise<void>;
  issue: (email: string) => Promise<string | undefined>;
  deliver: (email: string, otp: string) => Promise<void>;
}

export function normalizeEmail(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const email = raw.trim().toLowerCase();
  return z.email().safeParse(email).success ? email : null;
}

export function clientIp(headers: Headers): string | null {
  const forwarded = headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwarded || null;
}

export function hashForLimit(value: string): string {
  return createHmac("sha256", process.env.BETTER_AUTH_SECRET ?? "")
    .update(value)
    .digest("hex");
}

export async function requestOtp(
  rawEmail: unknown,
  ip: string | null,
  deps: OtpRequestDeps,
): Promise<OtpRequestResult> {
  const email = normalizeEmail(rawEmail);
  if (email === null) return { ok: false, error: { code: "INVALID_EMAIL" } };

  let sendId: string | null = null;
  if (!isDevFixedOtp(email)) {
    const reservation = await deps.reserve(
      hashForLimit(email),
      ip === null ? null : hashForLimit(ip),
    );
    if ("retryAfterSeconds" in reservation) {
      return {
        ok: false,
        error: {
          code: "OTP_SEND_LIMIT",
          retryAfterSeconds: reservation.retryAfterSeconds,
        },
      };
    }
    sendId = reservation.sendId;
  }

  try {
    const otp = await deps.issue(email);
    if (otp === undefined) throw new Error("No code was issued");
    await deps.deliver(email, otp);
  } catch (error) {
    console.error(
      `[otp] request failed: ${error instanceof Error ? error.message : "unknown"}`,
    );
    if (sendId !== null) await deps.cancel(sendId);
    return { ok: false, error: { code: "OTP_SEND_FAILED" } };
  }
  return { ok: true };
}
