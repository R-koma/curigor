import { describe, expect, it } from "vitest";

import { defaultNameFromEmail, withDefaultName } from "@/lib/auth-hooks";

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
