const API_BASE_URL =
  (typeof window === "undefined" && process.env.API_URL_INTERNAL) ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";
const AUTH_BASE_URL =
  process.env.NEXT_PUBLIC_BETTER_AUTH_URL || "http://localhost:3000";

export async function getToken(cookieHeader?: string): Promise<string> {
  const res = await fetch(`${AUTH_BASE_URL}/api/auth/token`, {
    headers: cookieHeader ? { Cookie: cookieHeader } : undefined,
  });
  if (!res.ok) throw new Error(`Token fetch failed: ${res.status}`);
  const { token } = await res.json();
  return token;
}

export async function fetchAPI<T>(
  path: string,
  options?: RequestInit & { token?: string },
): Promise<T> {
  const authToken = options?.token ?? (await getToken());

  const { token: _, ...restOptions } = options ?? {};
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...restOptions,
    headers: {
      Authorization: `Bearer ${authToken}`,
      "Content-Type": "application/json",
      ...restOptions?.headers,
    },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// 画像配信エンドポイントは Bearer 認証が必要で <img src> ではヘッダーを付与できない。
// 認証付きで blob を取得し object URL を返す。呼び出し側は不要になったら revoke する。
export async function fetchImageObjectURL(
  path: string,
  token?: string,
): Promise<string> {
  const authToken = token ?? (await getToken());
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${authToken}` },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return URL.createObjectURL(await res.blob());
}

export class TranscriptionError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`Transcription failed: ${status}`);
    this.status = status;
  }
}

export async function transcribeAudio(
  sessionId: string,
  audio: Blob,
  token?: string,
): Promise<string> {
  const authToken = token ?? (await getToken());
  const form = new FormData();
  form.append("dialogue_session_id", sessionId);
  form.append(
    "audio",
    audio,
    audio.type.startsWith("audio/mp4") ? "recording.mp4" : "recording.webm",
  );
  const res = await fetch(`${API_BASE_URL}/api/transcriptions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${authToken}` },
    body: form,
  });
  if (!res.ok) throw new TranscriptionError(res.status);
  const { text } = (await res.json()) as { text: string };
  return text;
}
