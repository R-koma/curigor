import "server-only";

import type { Pool } from "pg";

import { OTP_SEND_LIMITS, type Reservation } from "@/lib/otp-request";

export async function reserveOtpSend(
  pool: Pool,
  emailHash: string,
  ipHash: string | null,
): Promise<Reservation> {
  const { rows } = await pool.query<{
    send_id: string | null;
    retry_after_seconds: number | null;
  }>(
    "SELECT send_id, retry_after_seconds FROM reserve_email_otp_send($1, $2, $3, $4, $5, $6)",
    [
      emailHash,
      ipHash,
      OTP_SEND_LIMITS.ipHourly,
      OTP_SEND_LIMITS.pairHourly,
      OTP_SEND_LIMITS.pairDaily,
      OTP_SEND_LIMITS.emailDaily,
    ],
  );
  const row = rows[0];
  if (row?.send_id) return { sendId: row.send_id };
  return { retryAfterSeconds: row?.retry_after_seconds ?? 60 };
}

export async function cancelOtpSend(pool: Pool, sendId: string): Promise<void> {
  await pool.query("DELETE FROM email_otp_sends WHERE id = $1", [sendId]);
}
