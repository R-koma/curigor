import { mkdtemp, mkdir, readdir, writeFile } from "fs/promises";
import os from "os";
import path from "path";
import { describe, expect, it } from "vitest";

import { avatarsDir, deleteAvatarFiles } from "@/lib/avatar-files";

async function rootWith(files: string[]): Promise<string> {
  const root = await mkdtemp(path.join(os.tmpdir(), "avatars-"));
  await mkdir(avatarsDir(root), { recursive: true });
  await Promise.all(
    files.map((f) => writeFile(path.join(avatarsDir(root), f), "x")),
  );
  return root;
}

describe("deleteAvatarFiles", () => {
  it("removes the user's avatar of any extension and keeps others", async () => {
    const root = await rootWith(["u1.png", "u1.jpg", "u2.png"]);
    await deleteAvatarFiles("u1", root);
    expect(await readdir(avatarsDir(root))).toEqual(["u2.png"]);
  });

  it("also removes avatars saved with a timestamp suffix", async () => {
    const root = await rootWith(["u1-1778726377375.png", "u10.png"]);
    await deleteAvatarFiles("u1", root);
    expect(await readdir(avatarsDir(root))).toEqual(["u10.png"]);
  });

  it("succeeds when the avatar directory does not exist", async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), "avatars-"));
    await expect(deleteAvatarFiles("u1", root)).resolves.toBeUndefined();
  });

  it("succeeds when the user has no avatar", async () => {
    const root = await rootWith([]);
    await expect(deleteAvatarFiles("u1", root)).resolves.toBeUndefined();
  });
});
