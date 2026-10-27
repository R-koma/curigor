// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { verifyHuman } from "@/lib/human-check";

function siteverify(body: unknown, status = 200) {
  return vi.fn<typeof fetch>(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  );
}

beforeEach(() => {
  vi.stubEnv("TURNSTILE_SECRET_KEY", "secret-key");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("verifyHuman", () => {
  it("passes when Turnstile accepts the token", async () => {
    const fetchImpl = siteverify({ success: true });

    expect(await verifyHuman("token-1", "203.0.113.5", fetchImpl)).toBe(true);

    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe(
      "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    );
    expect(JSON.parse(String(init?.body))).toEqual({
      secret: "secret-key",
      response: "token-1",
      remoteip: "203.0.113.5",
    });
  });

  it("leaves out the IP when it is unknown", async () => {
    const fetchImpl = siteverify({ success: true });

    await verifyHuman("token-1", null, fetchImpl);

    expect(JSON.parse(String(fetchImpl.mock.calls[0][1]?.body))).toEqual({
      secret: "secret-key",
      response: "token-1",
    });
  });

  it("fails when Turnstile rejects the token", async () => {
    const fetchImpl = siteverify({
      success: false,
      "error-codes": ["invalid-input-response"],
    });

    expect(await verifyHuman("token-1", null, fetchImpl)).toBe(false);
  });

  it.each([undefined, null, "", 123, "x".repeat(2049)])(
    "fails without calling Turnstile for the token %o",
    async (token) => {
      const fetchImpl = siteverify({ success: true });

      expect(await verifyHuman(token, null, fetchImpl)).toBe(false);
      expect(fetchImpl).not.toHaveBeenCalled();
    },
  );

  it("fails closed when Turnstile cannot be reached", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () => {
      throw new TypeError("fetch failed");
    });

    expect(await verifyHuman("token-1", null, fetchImpl)).toBe(false);
  });

  it("fails closed on an error status", async () => {
    expect(
      await verifyHuman("token-1", null, siteverify({ success: true }, 500)),
    ).toBe(false);
  });

  it("fails closed in production without a secret", async () => {
    vi.stubEnv("TURNSTILE_SECRET_KEY", "");
    vi.stubEnv("NODE_ENV", "production");

    expect(await verifyHuman("token-1", null, siteverify({}))).toBe(false);
  });

  it("skips the check in development without a secret", async () => {
    vi.stubEnv("TURNSTILE_SECRET_KEY", "");
    vi.stubEnv("NODE_ENV", "development");
    const fetchImpl = siteverify({});

    expect(await verifyHuman(undefined, null, fetchImpl)).toBe(true);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
