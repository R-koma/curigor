import "server-only";

import { createHmac } from "node:crypto";

import * as z from "zod";

import { isDevFixedOtp } from "@/lib/dev-auth";

export const OTP_SEND_LIMITS = {
  ipHourly: 10,
  pairHourly: 5,
  pairDaily: 10,
  emailDaily: 30,
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

const GMAIL_DOMAINS = new Set(["gmail.com", "googlemail.com"]);

// 同じ受信箱に届く書き方（+タグ、Gmail の . と googlemail.com）を 1 つの宛先として数える
export function inboxKey(email: string): string {
  const at = email.lastIndexOf("@");
  let local = email.slice(0, at).split("+")[0];
  let domain = email.slice(at + 1);
  if (GMAIL_DOMAINS.has(domain)) {
    local = local.replaceAll(".", "");
    domain = "gmail.com";
  }
  return `${local}@${domain}`;
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
      hashForLimit(inboxKey(email)),
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
