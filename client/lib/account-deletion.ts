import { API_BASE_URL } from "@/lib/api";
import { deleteAvatarFiles } from "@/lib/avatar-files";

interface PurgeDeps {
  signToken: (userId: string) => Promise<string>;
  fetchImpl?: typeof fetch;
  avatarRoot?: string;
}

export async function purgeAccountData(
  userId: string,
  { signToken, fetchImpl = fetch, avatarRoot }: PurgeDeps,
): Promise<void> {
  const token = await signToken(userId);
  const res = await fetchImpl(`${API_BASE_URL}/api/account/data`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Account data purge failed: ${res.status}`);
  }
  await deleteAvatarFiles(userId, avatarRoot);
}
