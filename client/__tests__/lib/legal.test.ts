import { describe, expect, it } from "vitest";

import { operatorFromEnv } from "@/lib/legal";

describe("operatorFromEnv", () => {
  it("returns the operator when both name and email are set", () => {
    expect(
      operatorFromEnv({
        OPERATOR_NAME: " 運営 太郎 ",
        OPERATOR_EMAIL: "support@example.com",
      }),
    ).toEqual({ name: "運営 太郎", email: "support@example.com" });
  });

  it.each([
    {},
    { OPERATOR_NAME: "運営 太郎" },
    { OPERATOR_EMAIL: "support@example.com" },
    { OPERATOR_NAME: "  ", OPERATOR_EMAIL: "support@example.com" },
  ])("returns null unless both are non-empty: %o", (env) => {
    expect(operatorFromEnv(env)).toBeNull();
  });
});
