import { mkdtemp, mkdir, readdir, writeFile } from "fs/promises";
import os from "os";
import path from "path";
import { describe, expect, it, vi } from "vitest";

import { purgeAccountData } from "@/lib/account-deletion";
import { avatarsDir } from "@/lib/avatar-files";

async function rootWithAvatar(): Promise<string> {
  const root = await mkdtemp(path.join(os.tmpdir(), "purge-"));
  await mkdir(avatarsDir(root), { recursive: true });
  await writeFile(path.join(avatarsDir(root), "u1.png"), "x");
  return root;
}

describe("purgeAccountData", () => {
  it("calls the API with the signed token, then removes the avatar", async () => {
    const root = await rootWithAvatar();
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));

    await purgeAccountData("u1", {
      signToken: async (sub) => `token-for-${sub}`,
      fetchImpl,
      avatarRoot: root,
    });

    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toMatch(/\/api\/account\/data$/);
    expect(init).toMatchObject({
      method: "DELETE",
      headers: { Authorization: "Bearer token-for-u1" },
    });
    expect(await readdir(avatarsDir(root))).toEqual([]);
  });

  it("throws without touching the avatar when the API fails", async () => {
    const root = await rootWithAvatar();
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 500 }));

    await expect(
      purgeAccountData("u1", {
        signToken: async () => "t",
        fetchImpl,
        avatarRoot: root,
      }),
    ).rejects.toThrow();
    expect(await readdir(avatarsDir(root))).toEqual(["u1.png"]);
  });
});
