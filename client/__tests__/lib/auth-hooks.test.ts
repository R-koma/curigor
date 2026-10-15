import { describe, expect, it } from "vitest";

import {
  defaultNameFromEmail,
  withDefaultName,
  withoutOAuthTokens,
} from "@/lib/auth-hooks";

describe("defaultNameFromEmail", () => {
  it("uses the part before @", () => {
    expect(defaultNameFromEmail("taro.yamada@example.com")).toBe("taro.yamada");
  });

  it("falls back to the whole value without @", () => {
    expect(defaultNameFromEmail("taro")).toBe("taro");
  });
});

describe("withDefaultName", () => {
  it("fills an empty name", () => {
    expect(withDefaultName({ name: "", email: "dev@example.test" }).name).toBe(
      "dev",
    );
  });

  it("keeps an existing name", () => {
    expect(
      withDefaultName({ name: "山田 太郎", email: "taro@gmail.com" }).name,
    ).toBe("山田 太郎");
  });
});

describe("withoutOAuthTokens", () => {
  it("drops every OAuth token and expiry but keeps the account link", () => {
    const account = withoutOAuthTokens({
      accountId: "g-123",
      providerId: "google",
      accessToken: "a",
      refreshToken: "r",
      idToken: "i",
      accessTokenExpiresAt: new Date(),
      refreshTokenExpiresAt: new Date(),
    });
    expect(account).toMatchObject({
      accountId: "g-123",
      providerId: "google",
      accessToken: null,
      refreshToken: null,
      idToken: null,
      accessTokenExpiresAt: null,
      refreshTokenExpiresAt: null,
    });
  });
});
