import "server-only";

const SITEVERIFY_URL =
  "https://challenges.cloudflare.com/turnstile/v0/siteverify";
const VERIFY_TIMEOUT_MS = 5000;
const MAX_TOKEN_LENGTH = 2048;

export async function verifyHuman(
  token: unknown,
  ip: string | null,
  fetchImpl: typeof fetch = fetch,
): Promise<boolean> {
  const secret = process.env.TURNSTILE_SECRET_KEY;
  if (!secret) return process.env.NODE_ENV !== "production";
  if (
    typeof token !== "string" ||
    token === "" ||
    token.length > MAX_TOKEN_LENGTH
  ) {
    return false;
  }
  try {
    const res = await fetchImpl(SITEVERIFY_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        secret,
        response: token,
        ...(ip === null ? {} : { remoteip: ip }),
      }),
      signal: AbortSignal.timeout(VERIFY_TIMEOUT_MS),
    });
    if (!res.ok) return false;
    const body: { success?: unknown } = await res.json();
    return body.success === true;
  } catch {
    return false;
  }
}
