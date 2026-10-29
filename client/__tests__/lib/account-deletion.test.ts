import { describe, expect, it, vi } from "vitest";

import { deletionTokenPayload, purgeAccountData } from "@/lib/account-deletion";

describe("purgeAccountData", () => {
  it("calls the API with the signed token", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));

    await purgeAccountData("u1", {
      signToken: async (sub) => `token-for-${sub}`,
      fetchImpl,
    });

    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toMatch(/\/api\/account\/data$/);
    expect(init).toMatchObject({
      method: "DELETE",
      headers: { Authorization: "Bearer token-for-u1" },
    });
  });

  it("throws when the API fails so the user is not deleted", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 500 }));

    await expect(
      purgeAccountData("u1", { signToken: async () => "t", fetchImpl }),
    ).rejects.toThrow();
  });
});

describe("deletionTokenPayload", () => {
  it("marks the token as one for account deletion only", () => {
    expect(deletionTokenPayload("u1")).toEqual({
      sub: "u1",
      purpose: "account-deletion",
    });
  });
});
