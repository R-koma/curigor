import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  refresh: vi.fn(),
  push: vi.fn(),
  submitConsent: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mocks.replace,
    refresh: mocks.refresh,
    push: mocks.push,
  }),
}));

vi.mock("@/lib/consent", () => ({ submitConsent: mocks.submitConsent }));

vi.mock("@/lib/auth-client", () => ({
  authClient: { signOut: mocks.signOut },
}));

import { ConsentForm } from "@/components/consent/consent-form";
import { ApiError } from "@/lib/api";

const AGREE = /18 歳以上であり、利用規約とプライバシーポリシー/;

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ConsentForm", () => {
  it("cannot be submitted until the box is checked", async () => {
    render(<ConsentForm termsVersion={1} />);

    const button = screen.getByRole("button", { name: "同意して始める" });
    expect(button).toBeDisabled();

    await userEvent.click(screen.getByLabelText(AGREE));
    expect(button).toBeEnabled();
  });

  it("records consent to the shown version and goes to the dashboard", async () => {
    mocks.submitConsent.mockResolvedValue(undefined);
    render(<ConsentForm termsVersion={2} />);

    await userEvent.click(screen.getByLabelText(AGREE));
    await userEvent.click(
      screen.getByRole("button", { name: "同意して始める" }),
    );

    expect(mocks.submitConsent).toHaveBeenCalledWith(2);
    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/dashboard"),
    );
  });

  it("asks to read again when the terms were updated", async () => {
    mocks.submitConsent.mockRejectedValue(
      new ApiError(409, "terms_version_outdated", "Terms have been updated"),
    );
    render(<ConsentForm termsVersion={1} />);

    await userEvent.click(screen.getByLabelText(AGREE));
    await userEvent.click(
      screen.getByRole("button", { name: "同意して始める" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "規約が更新されました",
    );
    expect(mocks.refresh).toHaveBeenCalled();
    expect(screen.getByLabelText(AGREE)).not.toBeChecked();
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("tells the user to reload when the status could not be read", () => {
    render(<ConsentForm termsVersion={null} />);

    expect(screen.getByRole("alert")).toHaveTextContent("読み込めませんでした");
    expect(
      screen.getByRole("button", { name: "同意して始める" }),
    ).toBeDisabled();
  });

  it("links to the terms and the privacy policy", () => {
    render(<ConsentForm termsVersion={1} />);

    expect(screen.getByRole("link", { name: "利用規約" })).toHaveAttribute(
      "href",
      "/terms",
    );
    expect(
      screen.getByRole("link", { name: "プライバシーポリシー" }),
    ).toHaveAttribute("href", "/privacy");
  });
});
