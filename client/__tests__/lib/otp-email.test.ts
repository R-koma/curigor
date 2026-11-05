import { describe, expect, it } from "vitest";

import { buildOtpEmail } from "@/lib/email/otp-email";

describe("buildOtpEmail", () => {
  const message = buildOtpEmail("taro@example.com", "482913");

  it("addresses the recipient with a fixed subject", () => {
    expect(message.to).toBe("taro@example.com");
    expect(message.subject).toBe("ログインコード");
  });

  it("puts the code and its lifetime in both bodies", () => {
    for (const body of [message.text, message.html]) {
      expect(body).toContain("482913");
      expect(body).toContain("次のコードを 5 分以内に入力してください。");
      expect(body).toContain("このコードを他人に伝えないでください");
    }
  });

  it("starts the html with a hidden preview that does not reveal the code", () => {
    const body = message.html.slice(message.html.indexOf("<body"));
    const preview = body.match(/<div style="display:none[^>]*>(.*?)<\/div>/);
    expect(preview?.index ?? Infinity).toBeLessThan(body.indexOf("<table"));
    expect(preview?.[1]).toContain("5 分以内に入力してください");
    expect(preview?.[1]).not.toContain("482913");
  });

  it("does not repeat the service name in the text body", () => {
    expect(message.text).not.toContain("Curigor");
  });

  it("starts the text body with the code", () => {
    expect(message.text.startsWith("482913")).toBe(true);
  });

  it("contains no links", () => {
    expect(message.html).not.toMatch(/<a\s/i);
    expect(message.text).not.toMatch(/https?:\/\//);
    expect(message.html).not.toMatch(/https?:\/\//);
  });

  it("embeds the logo as an inline image the html refers to by content id", () => {
    const [logo] = message.inlineImages ?? [];
    expect(message.html).toContain(`src="cid:${logo.contentId}"`);
    expect(logo.content.subarray(1, 4).toString()).toBe("PNG");
    expect(
      logo.content.readUInt32BE(16) / logo.content.readUInt32BE(20),
    ).toBeCloseTo(29.75 / 17.5, 1);
  });
});
