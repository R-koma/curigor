import type { AuthErrorLike } from "@/lib/otp-error";

export async function requestSignInCode(
  email: string,
): Promise<{ error: AuthErrorLike | null }> {
  const res = await fetch("/api/otp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (res.ok) return { error: null };
  const body: { code?: string; retryAfterSeconds?: number } = await res
    .json()
    .catch(() => ({}));
  return {
    error: {
      code: body.code,
      status: res.status,
      retryAfterSeconds: body.retryAfterSeconds,
    },
  };
}
