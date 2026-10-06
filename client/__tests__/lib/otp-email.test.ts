import { describe, expect, it } from "vitest";

import { buildOtpEmail } from "@/lib/email/otp-email";

describe("buildOtpEmail", () => {
  const message = buildOtpEmail("taro@example.com", "482913");

  it("addresses the recipient with a fixed subject", () => {
    expect(message.to).toBe("taro@example.com");
    expect(message.subject).toBe("Curigor のログインコード");
  });

  it("puts the code and its lifetime in both bodies", () => {
    for (const body of [message.text, message.html]) {
      expect(body).toContain("482913");
      expect(body).toContain("5 分間有効です");
      expect(body).toContain("このコードを他人に伝えないでください");
    }
  });

  it("starts the text body with the code", () => {
    expect(message.text.startsWith("482913")).toBe(true);
  });

  it("contains no links", () => {
    expect(message.html).not.toMatch(/<a\s/i);
    expect(message.text).not.toMatch(/https?:\/\//);
    expect(message.html).not.toMatch(/https?:\/\//);
  });
});
