import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  type MockInstance,
  vi,
} from "vitest";

const sendEmail = vi.hoisted(() => vi.fn());
vi.mock("@/lib/email/send-email", () => ({ sendEmail }));

import { deliverOtp, emailOtpOptions } from "@/lib/auth-otp";

let info: MockInstance<typeof console.info>;

beforeEach(() => {
  sendEmail.mockReset();
  info = vi.spyOn(console, "info").mockImplementation(() => {});
});

afterEach(() => {
  info.mockRestore();
  vi.unstubAllEnvs();
});

describe("emailOtpOptions", () => {
  it("uses the agreed limits and hashes stored codes", () => {
    expect(emailOtpOptions).toMatchObject({
      otpLength: 6,
      expiresIn: 300,
      allowedAttempts: 3,
      storeOTP: "hashed",
    });
  });

  it("returns the fixed code only for dev addresses", () => {
    vi.stubEnv("DEV_FIXED_OTP", "true");
    const generate = emailOtpOptions.generateOTP!;
    expect(generate({ email: "dev@example.test", type: "sign-in" })).toBe(
      "000000",
    );
    expect(
      generate({ email: "victim@gmail.com", type: "sign-in" }),
    ).toBeUndefined();
  });
});

describe("deliverOtp", () => {
  it("does not send or print the code for dev addresses", async () => {
    vi.stubEnv("DEV_FIXED_OTP", "true");
    await deliverOtp("dev@example.test", "000000");
    expect(sendEmail).not.toHaveBeenCalled();
    expect(JSON.stringify(info.mock.calls)).not.toContain("000000");
  });

  it("prints the code in development without RESEND_API_KEY", async () => {
    vi.stubEnv("RESEND_API_KEY", "");
    await deliverOtp("taro@gmail.com", "482913");
    expect(sendEmail).not.toHaveBeenCalled();
    expect(JSON.stringify(info.mock.calls)).toContain("482913");
  });

  it("sends the email when RESEND_API_KEY is set", async () => {
    vi.stubEnv("RESEND_API_KEY", "re_test");
    await deliverOtp("taro@gmail.com", "482913");
    expect(sendEmail).toHaveBeenCalledWith(
      expect.objectContaining({ to: "taro@gmail.com" }),
    );
  });

  it("never prints the code in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("RESEND_API_KEY", "");
    sendEmail.mockRejectedValue(new Error("RESEND_API_KEY is required"));
    await expect(deliverOtp("taro@gmail.com", "482913")).rejects.toThrow();
    expect(JSON.stringify(info.mock.calls)).not.toContain("482913");
  });
});
