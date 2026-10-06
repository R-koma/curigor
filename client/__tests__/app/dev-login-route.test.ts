// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  isDevAutoLogin: vi.fn(),
  sendVerificationOTP: vi.fn(),
  signInEmailOTP: vi.fn(),
}));

vi.mock("@/lib/dev-auth", () => ({
  isDevAutoLogin: mocks.isDevAutoLogin,
  DEV_LOGIN_EMAIL: "dev@example.test",
  DEV_FIXED_OTP_CODE: "000000",
}));

vi.mock("@/lib/auth", () => ({
  auth: {
    api: {
      sendVerificationOTP: mocks.sendVerificationOTP,
      signInEmailOTP: mocks.signInEmailOTP,
    },
  },
}));

import { GET } from "@/app/api/dev/login/route";

function request(secFetchSite?: string) {
  const headers = new Headers();
  if (secFetchSite) headers.set("sec-fetch-site", secFetchSite);
  return new Request("http://localhost:3000/api/dev/login", { headers });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.isDevAutoLogin.mockReturnValue(true);
  mocks.signInEmailOTP.mockResolvedValue({
    headers: new Headers([
      ["set-cookie", "better-auth.session_token=abc; Path=/; HttpOnly"],
    ]),
    response: {},
  });
});

describe("GET /api/dev/login", () => {
  it("returns 404 when auto login is off", async () => {
    mocks.isDevAutoLogin.mockReturnValue(false);
    const response = await GET(request("none"));
    expect(response.status).toBe(404);
    expect(mocks.sendVerificationOTP).not.toHaveBeenCalled();
    expect(mocks.signInEmailOTP).not.toHaveBeenCalled();
  });

  it.each(["cross-site", "same-site"])(
    "returns 403 for Sec-Fetch-Site: %s",
    async (site) => {
      const response = await GET(request(site));
      expect(response.status).toBe(403);
      expect(mocks.sendVerificationOTP).not.toHaveBeenCalled();
      expect(mocks.signInEmailOTP).not.toHaveBeenCalled();
    },
  );

  it.each(["same-origin", "none", undefined])(
    "signs in the dev user for Sec-Fetch-Site: %s",
    async (site) => {
      const response = await GET(request(site));
      expect(mocks.sendVerificationOTP).toHaveBeenCalledWith({
        body: { email: "dev@example.test", type: "sign-in" },
      });
      expect(mocks.signInEmailOTP).toHaveBeenCalledWith({
        body: { email: "dev@example.test", otp: "000000" },
        returnHeaders: true,
      });
      expect(response.status).toBe(307);
      expect(response.headers.get("location")).toBe(
        "http://localhost:3000/dashboard",
      );
      expect(response.headers.get("set-cookie")).toContain(
        "better-auth.session_token=abc",
      );
    },
  );
});
