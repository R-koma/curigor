import { API_BASE_URL } from "@/lib/api";

// 値は server/api/dependencies.py の ACCOUNT_DELETION_PURPOSE と一致させる
const ACCOUNT_DELETION_PURPOSE = "account-deletion";

export function deletionTokenPayload(userId: string) {
  return { sub: userId, purpose: ACCOUNT_DELETION_PURPOSE };
}

interface PurgeDeps {
  signToken: (userId: string) => Promise<string>;
  fetchImpl?: typeof fetch;
}

export async function purgeAccountData(
  userId: string,
  { signToken, fetchImpl = fetch }: PurgeDeps,
): Promise<void> {
  const token = await signToken(userId);
  const res = await fetchImpl(`${API_BASE_URL}/api/account/data`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Account data purge failed: ${res.status}`);
  }
}
