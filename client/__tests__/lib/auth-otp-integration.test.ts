// @vitest-environment node
import { betterAuth } from "better-auth";
import { memoryAdapter } from "better-auth/adapters/memory";
import { emailOTP } from "better-auth/plugins";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  type MockInstance,
  vi,
} from "vitest";

import { authDatabaseHooks } from "@/lib/auth-hooks";
import { emailOtpOptions } from "@/lib/auth-otp";

type Row = Record<string, unknown>;

function createTestAuth() {
  const db: Record<string, Row[]> = {
    user: [],
    session: [],
    account: [],
    verification: [],
  };
  const auth = betterAuth({
    database: memoryAdapter(db),
    secret: "test-secret-test-secret-test-secret-0123",
    baseURL: "http://localhost:3000",
    databaseHooks: authDatabaseHooks,
    plugins: [emailOTP(emailOtpOptions)],
  });
  return { auth, db };
}

let info: MockInstance<typeof console.info>;

beforeEach(() => {
  info = vi.spyOn(console, "info").mockImplementation(() => {});
  vi.stubEnv("RESEND_API_KEY", "");
});

afterEach(() => {
  info.mockRestore();
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function requestCode(
  auth: ReturnType<typeof createTestAuth>["auth"],
  email: string,
) {
  await auth.api.sendVerificationOTP({ body: { email, type: "sign-in" } });
}

describe("the fixed development code through better-auth", () => {
  it.each([
    "victim@gmail.com",
    "dev@example.test.evil.com",
    "example.test@evil.com",
  ])("cannot sign in to %s with 000000", async (email) => {
    vi.stubEnv("DEV_FIXED_OTP", "true");
    const { auth, db } = createTestAuth();
    await requestCode(auth, email);
    await expect(
      auth.api.signInEmailOTP({ body: { email, otp: "000000" } }),
    ).rejects.toThrow();
    expect(db.session).toHaveLength(0);
  });

  it("signs in dev@example.test with 000000 and names the user", async () => {
    vi.stubEnv("DEV_FIXED_OTP", "true");
    const { auth, db } = createTestAuth();
    await requestCode(auth, "dev@example.test");
    await auth.api.signInEmailOTP({
      body: { email: "dev@example.test", otp: "000000" },
    });
    expect(db.session).toHaveLength(1);
    expect(db.user[0]).toMatchObject({
      email: "dev@example.test",
      name: "dev",
      emailVerified: true,
    });
  });

  it("rejects 000000 for dev@example.test when DEV_FIXED_OTP is off", async () => {
    vi.stubEnv("DEV_FIXED_OTP", "");
    const { auth, db } = createTestAuth();
    await requestCode(auth, "dev@example.test");
    await expect(
      auth.api.signInEmailOTP({
        body: { email: "dev@example.test", otp: "000000" },
      }),
    ).rejects.toThrow();
    expect(db.session).toHaveLength(0);
  });

  it("refuses to load in production with DEV_FIXED_OTP set", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("DEV_FIXED_OTP", "true");
    vi.resetModules();
    await expect(import("@/lib/auth-otp")).rejects.toThrow("DEV_FIXED_OTP");
  });
});

describe("the random code through better-auth", () => {
  it("signs in with the issued code and stores only its hash", async () => {
    const { auth, db } = createTestAuth();
    await requestCode(auth, "taro@gmail.com");

    const printed = JSON.stringify(info.mock.calls).match(/\b\d{6}\b/);
    expect(printed).not.toBeNull();
    const otp = printed![0];
    expect(String(db.verification[0].value)).not.toContain(otp);

    await auth.api.signInEmailOTP({ body: { email: "taro@gmail.com", otp } });
    expect(db.session).toHaveLength(1);
    expect(db.user[0]).toMatchObject({ name: "taro" });
  });
});
