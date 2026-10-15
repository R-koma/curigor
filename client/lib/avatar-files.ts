import { readdir, rm } from "fs/promises";
import path from "path";

export function avatarsDir(root: string = process.cwd()): string {
  return path.join(root, "public", "avatars");
}

export function safeAvatarUserId(userId: string): string {
  return userId.replace(/[^a-zA-Z0-9_-]/g, "");
}

async function listAvatarFiles(dir: string): Promise<string[]> {
  try {
    return await readdir(dir);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }
}

export async function deleteAvatarFiles(
  userId: string,
  root: string = process.cwd(),
): Promise<void> {
  const safeUserId = safeAvatarUserId(userId);
  if (!safeUserId) return;
  const dir = avatarsDir(root);
  const owned = (await listAvatarFiles(dir)).filter(
    (name) =>
      name.startsWith(`${safeUserId}.`) || name.startsWith(`${safeUserId}-`),
  );
  await Promise.all(
    owned.map((name) => rm(path.join(dir, name), { force: true })),
  );
}
