import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getToken: vi.fn(async () => "token-1"),
  fetchAPI: vi.fn(async () => undefined),
}));

vi.mock("@/lib/api", () => ({
  API_BASE_URL: "https://api.example.com",
  getToken: mocks.getToken,
  fetchAPI: mocks.fetchAPI,
}));

import { MAX_AVATAR_BYTES, removeAvatar, uploadAvatar } from "@/lib/avatar";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const file = new File([new Uint8Array([1, 2, 3])], "a.png", {
  type: "image/png",
});

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("uploadAvatar", () => {
  it("uploads the file to the API with the token and returns the full URL", async () => {
    fetchMock.mockResolvedValue(json({ path: "/api/avatars/u1/abc.png" }));

    const url = await uploadAvatar(file);

    expect(url).toBe("https://api.example.com/api/avatars/u1/abc.png");
    const [target, init] = fetchMock.mock.calls[0];
    expect(target).toBe("https://api.example.com/api/account/avatar");
    expect(init.method).toBe("PUT");
    expect(init.headers).toEqual({ Authorization: "Bearer token-1" });
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it.each([
    ["avatar_too_large", 413, "ファイルサイズは5MB以下にしてください"],
    [
      "unsupported_avatar_format",
      415,
      "JPEG, PNG, WebP のみアップロードできます",
    ],
    [
      "something_else",
      500,
      "写真をアップロードできませんでした。もう一度お試しください",
    ],
  ])("explains the %s error", async (code, status, message) => {
    fetchMock.mockResolvedValue(json({ code }, status));

    await expect(uploadAvatar(file)).rejects.toThrow(message);
  });

  it("refuses a file over the limit without calling the API", async () => {
    const big = new File([new Uint8Array(MAX_AVATAR_BYTES + 1)], "big.png");

    await expect(uploadAvatar(big)).rejects.toThrow(
      "ファイルサイズは5MB以下にしてください",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("removeAvatar", () => {
  it("deletes the avatar through the API", async () => {
    await removeAvatar();

    expect(mocks.fetchAPI).toHaveBeenCalledWith("/api/account/avatar", {
      method: "DELETE",
    });
  });
});
