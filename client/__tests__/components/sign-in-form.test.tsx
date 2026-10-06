import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  sendVerificationOtp: vi.fn(),
  signInEmailOtp: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/auth-client", () => ({
  authClient: {
    emailOtp: { sendVerificationOtp: mocks.sendVerificationOtp },
    signIn: { emailOtp: mocks.signInEmailOtp, social: vi.fn() },
  },
}));

import { SignInForm } from "@/components/auth/sign-in-form";

const OK = { data: { success: true }, error: null };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.sendVerificationOtp.mockResolvedValue(OK);
  mocks.signInEmailOtp.mockResolvedValue({ data: {}, error: null });
});

function codeInput() {
  return screen.getByLabelText("確認コード");
}

async function goToCodeStep(email = "taro@example.com") {
  const user = userEvent.setup();
  render(<SignInForm showDevCodeHint={false} />);
  await user.type(screen.getByLabelText("メールアドレス"), email);
  await user.click(screen.getByRole("button", { name: "続ける" }));
  await screen.findByLabelText("確認コード");
  return user;
}

describe("SignInForm: email step", () => {
  it("labels the email field and lets the browser autofill it", () => {
    render(<SignInForm showDevCodeHint={false} />);
    const input = screen.getByLabelText("メールアドレス");
    expect(input).toHaveAttribute("type", "email");
    expect(input).toHaveAttribute("autocomplete", "email");
  });

  it("trims the address before requesting a code", async () => {
    await goToCodeStep("  Taro@Example.com  ");
    expect(mocks.sendVerificationOtp).toHaveBeenCalledWith({
      email: "Taro@Example.com",
      type: "sign-in",
    });
  });

  it("validates on submit only", async () => {
    const user = userEvent.setup();
    render(<SignInForm showDevCodeHint={false} />);
    await user.type(screen.getByLabelText("メールアドレス"), "taro");
    expect(screen.queryByRole("alert")).toBeNull();
    await user.click(screen.getByRole("button", { name: "続ける" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "有効なメールアドレスを入力してください。",
    );
    expect(mocks.sendVerificationOtp).not.toHaveBeenCalled();
  });

  it("stays on the email step and keeps the input when sending fails", async () => {
    mocks.sendVerificationOtp.mockResolvedValue({
      data: null,
      error: { status: 429 },
    });
    const user = userEvent.setup();
    render(<SignInForm showDevCodeHint={false} />);
    await user.type(
      screen.getByLabelText("メールアドレス"),
      "taro@example.com",
    );
    await user.click(screen.getByRole("button", { name: "続ける" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "しばらく待ってからお試しください",
    );
    expect(screen.getByLabelText("メールアドレス")).toHaveValue(
      "taro@example.com",
    );
  });
});

describe("SignInForm: code step", () => {
  it("announces where the code went and focuses the code field", async () => {
    await goToCodeStep();
    expect(screen.getByRole("status")).toHaveTextContent(
      "taro@example.com に 6 桁のコードを送りました",
    );
    expect(codeInput()).toHaveFocus();
    expect(codeInput()).toHaveAttribute("autocomplete", "one-time-code");
    expect(codeInput()).toHaveAttribute("inputmode", "numeric");
  });

  it("signs in as soon as six digits are entered", async () => {
    const user = await goToCodeStep();
    await user.type(codeInput(), "482913");
    await waitFor(() =>
      expect(mocks.signInEmailOtp).toHaveBeenCalledWith({
        email: "taro@example.com",
        otp: "482913",
      }),
    );
    expect(mocks.push).toHaveBeenCalledWith("/dashboard");
  });

  it("accepts a pasted code with separators", async () => {
    const user = await goToCodeStep();
    await user.click(codeInput());
    await user.paste("482-913");
    await waitFor(() =>
      expect(mocks.signInEmailOtp).toHaveBeenCalledWith({
        email: "taro@example.com",
        otp: "482913",
      }),
    );
  });

  it("verifies only once while a check is in flight", async () => {
    let resolve: (value: unknown) => void = () => {};
    mocks.signInEmailOtp.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    const user = await goToCodeStep();
    await user.type(codeInput(), "482913");
    await user.type(codeInput(), "{Backspace}3");
    await act(async () => resolve({ data: {}, error: null }));
    expect(mocks.signInEmailOtp).toHaveBeenCalledTimes(1);
  });

  it("clears a wrong code and keeps the focus in the field", async () => {
    mocks.signInEmailOtp.mockResolvedValue({
      data: null,
      error: { code: "INVALID_OTP", status: 400 },
    });
    const user = await goToCodeStep();
    await user.type(codeInput(), "111111");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "コードが正しくありません",
    );
    expect(codeInput()).toHaveValue("");
    expect(codeInput()).toHaveFocus();
    expect(codeInput()).toHaveAttribute("aria-invalid", "true");
  });

  it("keeps the code for other errors", async () => {
    mocks.signInEmailOtp.mockResolvedValue({
      data: null,
      error: { code: "TOO_MANY_ATTEMPTS", status: 403 },
    });
    const user = await goToCodeStep();
    await user.type(codeInput(), "111111");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "試行回数の上限に達しました。コードを再送してください",
    );
    expect(codeInput()).toHaveValue("111111");
  });

  it("explains a verify failure without an error code as a sign-in problem", async () => {
    mocks.signInEmailOtp.mockResolvedValue({
      data: null,
      error: { status: 500 },
    });
    const user = await goToCodeStep();
    await user.type(codeInput(), "482913");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "ログインできませんでした。時間をおいて再度お試しください",
    );
  });

  it("goes back with the email address kept", async () => {
    const user = await goToCodeStep();
    await user.click(
      screen.getByRole("button", { name: "メールアドレスを変更" }),
    );
    expect(screen.getByLabelText("メールアドレス")).toHaveValue(
      "taro@example.com",
    );
  });

  it("shows the dev code hint only when asked", async () => {
    const user = userEvent.setup();
    render(<SignInForm showDevCodeHint />);
    await user.type(
      screen.getByLabelText("メールアドレス"),
      "dev@example.test",
    );
    await user.click(screen.getByRole("button", { name: "続ける" }));
    expect(
      await screen.findByText(
        "開発用: @example.test のアドレスはコード 000000",
      ),
    ).toBeInTheDocument();
  });

  it("hides the dev code hint by default", async () => {
    await goToCodeStep();
    expect(screen.queryByText(/開発用/)).toBeNull();
  });
});

describe("SignInForm: resend", () => {
  it("disables resend for 60 seconds, then resends and resets the step", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      mocks.signInEmailOtp.mockResolvedValue({
        data: null,
        error: { code: "OTP_EXPIRED", status: 400 },
      });
      const user = userEvent.setup({
        advanceTimers: vi.advanceTimersByTime,
      });
      render(<SignInForm showDevCodeHint={false} />);
      await user.type(
        screen.getByLabelText("メールアドレス"),
        "taro@example.com",
      );
      await user.click(screen.getByRole("button", { name: "続ける" }));
      await screen.findByLabelText("確認コード");

      expect(
        screen.getByRole("button", { name: "コードを再送（60 秒後）" }),
      ).toBeDisabled();

      await user.type(codeInput(), "111111");
      await screen.findByRole("alert");

      for (let second = 0; second < 60; second++) {
        act(() => vi.advanceTimersByTime(1000));
      }
      const resend = screen.getByRole("button", { name: "コードを再送" });
      expect(resend).toBeEnabled();
      await user.click(resend);

      expect(mocks.sendVerificationOtp).toHaveBeenCalledTimes(2);
      expect(await screen.findByRole("status")).toHaveTextContent(
        "taro@example.com にコードを再送しました",
      );
      expect(screen.queryByRole("alert")).toBeNull();
      expect(codeInput()).toHaveValue("");
      expect(
        screen.getByRole("button", { name: "コードを再送（60 秒後）" }),
      ).toBeDisabled();
    } finally {
      vi.useRealTimers();
    }
  });
});
