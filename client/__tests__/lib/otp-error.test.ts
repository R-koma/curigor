import { describe, expect, it } from "vitest";

import { otpErrorMessage } from "@/lib/otp-error";

describe("otpErrorMessage", () => {
  it.each([
    ["INVALID_OTP", "コードが正しくありません"],
    ["OTP_EXPIRED", "コードの有効期限が切れました。再送してください"],
    [
      "TOO_MANY_ATTEMPTS",
      "試行回数の上限に達しました。コードを再送してください",
    ],
  ])("maps %s", (code, message) => {
    expect(otpErrorMessage({ code, status: 400 }, "verify")).toBe(message);
  });

  it("maps rate limiting in both stages", () => {
    for (const stage of ["send", "verify"] as const) {
      expect(otpErrorMessage({ status: 429 }, stage)).toBe(
        "しばらく待ってからお試しください",
      );
    }
  });

  it.each([
    [59, "約 1 分"],
    [1500, "約 25 分"],
    [3600, "約 1 時間"],
    [3601, "約 2 時間"],
    [22 * 3600, "約 22 時間"],
  ])("tells the wait for a send limit of %i seconds", (seconds, wait) => {
    expect(
      otpErrorMessage(
        { code: "OTP_SEND_LIMIT", status: 429, retryAfterSeconds: seconds },
        "send",
      ),
    ).toBe(
      `コードを送れる回数の上限に達しました。${wait}後にもう一度お試しください`,
    );
  });

  it("explains a failed delivery as a delivery problem", () => {
    expect(
      otpErrorMessage({ code: "OTP_SEND_FAILED", status: 502 }, "send"),
    ).toBe("メールを送れませんでした。時間をおいて再度お試しください");
  });

  it("maps an invalid email", () => {
    expect(
      otpErrorMessage({ code: "INVALID_EMAIL", status: 400 }, "send"),
    ).toBe("有効なメールアドレスを入力してください。");
  });

  it("explains unknown send failures as a delivery problem", () => {
    expect(otpErrorMessage({ status: 500 }, "send")).toBe(
      "メールを送れませんでした。時間をおいて再度お試しください",
    );
  });

  it("explains unknown verify failures as a sign-in problem", () => {
    expect(otpErrorMessage({}, "verify")).toBe(
      "ログインできませんでした。時間をおいて再度お試しください",
    );
  });
});
