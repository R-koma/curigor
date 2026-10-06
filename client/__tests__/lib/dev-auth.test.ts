import { afterEach, describe, expect, it, vi } from "vitest";

import {
  assertDevAuthConfig,
  isDevAutoLogin,
  isDevFixedOtp,
  isDevFixedOtpEnabled,
} from "@/lib/dev-auth";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("isDevFixedOtp", () => {
  it("is true only for @example.test addresses when DEV_FIXED_OTP=true outside production", () => {
    vi.stubEnv("DEV_FIXED_OTP", "true");
    expect(isDevFixedOtp("dev@example.test")).toBe(true);
    expect(isDevFixedOtp("DEV@EXAMPLE.TEST")).toBe(true);
    expect(isDevFixedOtp("victim@gmail.com")).toBe(false);
    expect(isDevFixedOtp("dev@example.test.evil.com")).toBe(false);
    expect(isDevFixedOtp("example.test@evil.com")).toBe(false);
  });

  it("is false when DEV_FIXED_OTP is not true", () => {
    vi.stubEnv("DEV_FIXED_OTP", "");
    expect(isDevFixedOtp("dev@example.test")).toBe(false);
    vi.stubEnv("DEV_FIXED_OTP", "1");
    expect(isDevFixedOtp("dev@example.test")).toBe(false);
  });

  it("is false in production", () => {
    vi.stubEnv("DEV_FIXED_OTP", "true");
    vi.stubEnv("NODE_ENV", "production");
    expect(isDevFixedOtp("dev@example.test")).toBe(false);
    expect(isDevFixedOtpEnabled()).toBe(false);
  });
});

describe("isDevAutoLogin", () => {
  it("follows DEV_AUTO_LOGIN outside production", () => {
    vi.stubEnv("DEV_AUTO_LOGIN", "true");
    expect(isDevAutoLogin()).toBe(true);
    vi.stubEnv("NODE_ENV", "production");
    expect(isDevAutoLogin()).toBe(false);
  });
});

describe("assertDevAuthConfig", () => {
  it("accepts the development combinations", () => {
    vi.stubEnv("DEV_FIXED_OTP", "true");
    vi.stubEnv("DEV_AUTO_LOGIN", "true");
    expect(() => assertDevAuthConfig()).not.toThrow();
  });

  it("accepts production without the dev variables", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("DEV_FIXED_OTP", "");
    vi.stubEnv("DEV_AUTO_LOGIN", "");
    expect(() => assertDevAuthConfig()).not.toThrow();
  });

  it.each(["DEV_FIXED_OTP", "DEV_AUTO_LOGIN"])(
    "rejects %s in production",
    (name) => {
      vi.stubEnv("NODE_ENV", "production");
      vi.stubEnv(name, "true");
      expect(() => assertDevAuthConfig()).toThrow(name);
    },
  );

  it("rejects DEV_AUTO_LOGIN without DEV_FIXED_OTP", () => {
    vi.stubEnv("DEV_AUTO_LOGIN", "true");
    vi.stubEnv("DEV_FIXED_OTP", "");
    expect(() => assertDevAuthConfig()).toThrow("DEV_FIXED_OTP");
  });

  it("runs when the module is loaded", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("DEV_FIXED_OTP", "true");
    vi.resetModules();
    await expect(import("@/lib/dev-auth")).rejects.toThrow("DEV_FIXED_OTP");
  });
});
