import { API_BASE_URL, fetchAPI, getToken } from "@/lib/api";

export const MAX_AVATAR_BYTES = 5 * 1024 * 1024;
export const AVATAR_ACCEPT = "image/jpeg,image/png,image/webp";

const MESSAGES_BY_CODE: Record<string, string> = {
  avatar_too_large: "ファイルサイズは5MB以下にしてください",
  unsupported_avatar_format: "JPEG, PNG, WebP のみアップロードできます",
  avatar_empty: "空のファイルはアップロードできません",
};
const UPLOAD_FAILED =
  "写真をアップロードできませんでした。もう一度お試しください";

export async function uploadAvatar(file: File): Promise<string> {
  if (file.size > MAX_AVATAR_BYTES) {
    throw new Error(MESSAGES_BY_CODE.avatar_too_large);
  }
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_BASE_URL}/api/account/avatar`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${await getToken()}` },
    body,
  });
  if (!res.ok) {
    const error: { code?: unknown } = await res.json().catch(() => ({}));
    const message =
      typeof error.code === "string" ? MESSAGES_BY_CODE[error.code] : null;
    throw new Error(message ?? UPLOAD_FAILED);
  }
  const { path }: { path: string } = await res.json();
  return `${API_BASE_URL}${path}`;
}

export async function removeAvatar(): Promise<void> {
  await fetchAPI<void>("/api/account/avatar", { method: "DELETE" });
}
