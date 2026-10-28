// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clientIp,
  hashForLimit,
  inboxKey,
  normalizeEmail,
  type OtpRequestDeps,
  requestOtp,
} from "@/lib/otp-request";

function fakeDeps() {
  return {
    verifyHuman: vi.fn<OtpRequestDeps["verifyHuman"]>(async () => true),
    reserve: vi.fn<OtpRequestDeps["reserve"]>(async () => ({ sendId: "s1" })),
    cancel: vi.fn<OtpRequestDeps["cancel"]>(async () => {}),
    issue: vi.fn<OtpRequestDeps["issue"]>(async () => "482913"),
    deliver: vi.fn<OtpRequestDeps["deliver"]>(async () => {}),
  };
}

beforeEach(() => {
  vi.stubEnv("BETTER_AUTH_SECRET", "test-secret");
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("requestOtp", () => {
  it("reserves, issues and delivers a code to the normalized address", async () => {
    const deps = fakeDeps();

    const result = await requestOtp(" Taro@Gmail.com ", "203.0.113.5", deps);

    expect(result).toEqual({ ok: true });
    expect(deps.reserve).toHaveBeenCalledWith(
      hashForLimit("taro@gmail.com"),
      hashForLimit("203.0.113.5"),
    );
    expect(deps.issue).toHaveBeenCalledWith("taro@gmail.com");
    expect(deps.deliver).toHaveBeenCalledWith("taro@gmail.com", "482913");
    expect(deps.cancel).not.toHaveBeenCalled();
  });

  it("never records the address or the IP in clear text", async () => {
    const deps = fakeDeps();

    await requestOtp("taro@gmail.com", "203.0.113.5", deps);

    const [emailHash, ipHash] = deps.reserve.mock.calls[0];
    expect(emailHash).not.toContain("taro");
    expect(ipHash).not.toContain("203.0.113.5");
  });

  it("reserves without an IP when none is known", async () => {
    const deps = fakeDeps();

    await requestOtp("taro@gmail.com", null, deps);

    expect(deps.reserve).toHaveBeenCalledWith(
      hashForLimit("taro@gmail.com"),
      null,
    );
  });

  it("refuses an invalid address before reserving", async () => {
    const deps = fakeDeps();

    const result = await requestOtp("taro", "203.0.113.5", deps);

    expect(result).toEqual({ ok: false, error: { code: "INVALID_EMAIL" } });
    expect(deps.reserve).not.toHaveBeenCalled();
  });

  it("refuses a request that fails the human check before reserving", async () => {
    const deps = fakeDeps();
    deps.verifyHuman.mockResolvedValue(false);

    const result = await requestOtp("taro@gmail.com", "203.0.113.5", deps);

    expect(result).toEqual({
      ok: false,
      error: { code: "HUMAN_CHECK_FAILED" },
    });
    expect(deps.reserve).not.toHaveBeenCalled();
    expect(deps.issue).not.toHaveBeenCalled();
  });

  it("does not run the human check for an invalid address", async () => {
    const deps = fakeDeps();

    await requestOtp("taro", "203.0.113.5", deps);

    expect(deps.verifyHuman).not.toHaveBeenCalled();
  });

  it("returns the wait without issuing a code at the limit", async () => {
    const deps = fakeDeps();
    deps.reserve.mockResolvedValue({ retryAfterSeconds: 1500 });

    const result = await requestOtp("taro@gmail.com", "203.0.113.5", deps);

    expect(result).toEqual({
      ok: false,
      error: { code: "OTP_SEND_LIMIT", retryAfterSeconds: 1500 },
    });
    expect(deps.issue).not.toHaveBeenCalled();
    expect(deps.deliver).not.toHaveBeenCalled();
  });

  it("reports a failed delivery and gives the reservation back", async () => {
    const deps = fakeDeps();
    deps.deliver.mockRejectedValue(
      new Error("Email send failed: rate_limit_exceeded"),
    );

    const result = await requestOtp("taro@gmail.com", "203.0.113.5", deps);

    expect(result).toEqual({ ok: false, error: { code: "OTP_SEND_FAILED" } });
    expect(deps.cancel).toHaveBeenCalledWith("s1");
  });

  it("reports a failure when no code was issued", async () => {
    const deps = fakeDeps();
    deps.issue.mockResolvedValue(undefined);

    const result = await requestOtp("taro@gmail.com", "203.0.113.5", deps);

    expect(result).toEqual({ ok: false, error: { code: "OTP_SEND_FAILED" } });
    expect(deps.deliver).not.toHaveBeenCalled();
    expect(deps.cancel).toHaveBeenCalledWith("s1");
  });

  it("does not count development addresses", async () => {
    vi.stubEnv("DEV_FIXED_OTP", "true");
    const deps = fakeDeps();

    const result = await requestOtp("dev@example.test", "127.0.0.1", deps);

    expect(result).toEqual({ ok: true });
    expect(deps.reserve).not.toHaveBeenCalled();
  });
});

describe("inboxKey", () => {
  it.each([
    ["taro+test@example.com", "taro@example.com"],
    ["t.a.r.o@gmail.com", "taro@gmail.com"],
    ["t.a.r.o+x@googlemail.com", "taro@gmail.com"],
    ["t.a.r.o@example.com", "t.a.r.o@example.com"],
  ])("counts %s as %s", (email, key) => {
    expect(inboxKey(email)).toBe(key);
  });

  it("counts every spelling of one inbox against the same limit", async () => {
    const deps = fakeDeps();

    await requestOtp("T.aro+1@Gmail.com", null, deps);
    await requestOtp("taro@googlemail.com", null, deps);

    expect(deps.reserve.mock.calls[0][0]).toBe(deps.reserve.mock.calls[1][0]);
    expect(deps.deliver.mock.calls[0][0]).toBe("t.aro+1@gmail.com");
  });
});

describe("normalizeEmail", () => {
  it.each([123, null, "", "taro@", "@gmail.com"])("rejects %o", (raw) => {
    expect(normalizeEmail(raw)).toBeNull();
  });
});

describe("clientIp", () => {
  it("takes the first forwarded address", () => {
    const headers = new Headers({
      "x-forwarded-for": "203.0.113.5, 10.0.0.1",
    });
    expect(clientIp(headers)).toBe("203.0.113.5");
  });

  it("returns null without a forwarded address", () => {
    expect(clientIp(new Headers())).toBeNull();
  });
});
