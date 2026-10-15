import { rm } from "fs/promises";
import path from "path";

const AVATAR_EXTENSIONS = ["jpg", "png", "webp", "gif"] as const;

export function avatarsDir(root: string = process.cwd()): string {
  return path.join(root, "public", "avatars");
}

export function safeAvatarUserId(userId: string): string {
  return userId.replace(/[^a-zA-Z0-9_-]/g, "");
}

export async function deleteAvatarFiles(
  userId: string,
  root: string = process.cwd(),
): Promise<void> {
  const safeUserId = safeAvatarUserId(userId);
  if (!safeUserId) return;
  const dir = avatarsDir(root);
  await Promise.all(
    AVATAR_EXTENSIONS.map((ext) =>
      rm(path.join(dir, `${safeUserId}.${ext}`), { force: true }),
    ),
  );
}
