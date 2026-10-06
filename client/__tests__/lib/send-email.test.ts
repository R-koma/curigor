import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const send = vi.hoisted(() => vi.fn());

vi.mock("resend", () => ({
  Resend: class {
    emails = { send };
  },
}));

import { sendEmail } from "@/lib/email/send-email";

const MESSAGE = {
  to: "taro@example.com",
  subject: "件名",
  text: "本文",
  html: "<p>本文</p>",
};

beforeEach(() => {
  send.mockReset();
  vi.stubEnv("RESEND_API_KEY", "re_test");
  vi.stubEnv("EMAIL_FROM", "Curigor <noreply@auth.example.com>");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("sendEmail", () => {
  it("sends through Resend from EMAIL_FROM", async () => {
    send.mockResolvedValue({ data: { id: "1" }, error: null });
    await sendEmail(MESSAGE);
    expect(send).toHaveBeenCalledWith({
      from: "Curigor <noreply@auth.example.com>",
      ...MESSAGE,
    });
  });

  it.each(["RESEND_API_KEY", "EMAIL_FROM"])(
    "throws when %s is missing",
    async (name) => {
      vi.stubEnv(name, "");
      await expect(sendEmail(MESSAGE)).rejects.toThrow(name);
      expect(send).not.toHaveBeenCalled();
    },
  );

  it("throws without logging the body when Resend reports an error", async () => {
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => {});
    send.mockResolvedValue({
      data: null,
      error: { name: "validation_error", message: "bad from" },
    });
    await expect(sendEmail(MESSAGE)).rejects.toThrow("validation_error");
    expect(JSON.stringify(errorLog.mock.calls)).not.toContain("本文");
    errorLog.mockRestore();
  });
});
