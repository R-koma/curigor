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
import { DISABLED_EMAIL_OTP_PATHS, emailOtpOptions } from "@/lib/auth-otp";

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
    disabledPaths: DISABLED_EMAIL_OTP_PATHS,
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
  ])("cannot sign in to %s with the fixed development code", async (email) => {
    vi.stubEnv("DEV_FIXED_OTP", "true");
    const { auth, db } = createTestAuth();
    await requestCode(auth, email);
    await expect(
      auth.api.signInEmailOTP({ body: { email, otp: "000000" } }),
    ).rejects.toMatchObject({ body: { code: "INVALID_OTP" } });
    expect(db.verification).toHaveLength(1);
    expect(db.session).toHaveLength(0);
  });

  it("signs in a development address with the fixed code and names the user", async () => {
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

  it("rejects the fixed code for a development address when the switch is off", async () => {
    vi.stubEnv("DEV_FIXED_OTP", "");
    const { auth, db } = createTestAuth();
    await requestCode(auth, "dev@example.test");
    await expect(
      auth.api.signInEmailOTP({
        body: { email: "dev@example.test", otp: "000000" },
      }),
    ).rejects.toMatchObject({ body: { code: "INVALID_OTP" } });
    expect(db.verification).toHaveLength(1);
    expect(db.session).toHaveLength(0);
  });

  it("refuses to load in production with the development switch set", async () => {
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

describe("the plugin's other HTTP endpoints", () => {
  function post(
    auth: ReturnType<typeof createTestAuth>["auth"],
    path: string,
    body: Record<string, unknown>,
  ) {
    return auth.handler(
      new Request(`http://localhost:3000/api/auth${path}`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          origin: "http://localhost:3000",
        },
        body: JSON.stringify(body),
      }),
    );
  }

  const ALLOWED_PATHS = [
    "/email-otp/send-verification-otp",
    "/sign-in/email-otp",
  ];
  const pluginPaths = Object.values(emailOTP(emailOtpOptions).endpoints)
    .map((endpoint) => (endpoint as { path?: string }).path)
    .filter((path): path is string => typeof path === "string");

  it("disables every path the plugin registers except the two in use", () => {
    expect(pluginPaths).toEqual(expect.arrayContaining(ALLOWED_PATHS));
    expect([...DISABLED_EMAIL_OTP_PATHS].sort()).toEqual(
      pluginPaths.filter((path) => !ALLOWED_PATHS.includes(path)).sort(),
    );
  });

  it.each(DISABLED_EMAIL_OTP_PATHS)(
    "answers 404 and delivers nothing for %s",
    async (path) => {
      const { auth, db } = createTestAuth();
      const res = await post(auth, path, {
        email: "taro@gmail.com",
        otp: "123456",
        newEmail: "new@gmail.com",
        password: "password-1234",
      });
      expect(res.status).toBe(404);
      expect(info).not.toHaveBeenCalled();
      expect(db.verification).toHaveLength(0);
    },
  );

  it("keeps the code request endpoint for sign-in open", async () => {
    const { auth } = createTestAuth();
    const res = await post(auth, "/email-otp/send-verification-otp", {
      email: "taro@gmail.com",
      type: "sign-in",
    });
    expect(res.status).toBe(200);
    expect(JSON.stringify(info.mock.calls)).toMatch(/\b\d{6}\b/);
  });

  it("keeps the sign-in endpoint reachable", async () => {
    const { auth } = createTestAuth();
    const res = await post(auth, "/sign-in/email-otp", {
      email: "taro@gmail.com",
      otp: "123456",
    });
    expect(res.status).not.toBe(404);
  });

  it.each(["forget-password", "email-verification"] as const)(
    "does not deliver a %s code requested through the api",
    async (type) => {
      const { auth } = createTestAuth();
      await auth.api.sendVerificationOTP({
        body: { email: "taro@gmail.com", type },
      });
      expect(info).not.toHaveBeenCalled();
    },
  );
});
