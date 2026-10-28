import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DeleteAccountSection } from "@/components/settings/delete-account-section";

vi.mock("@/hooks/use-account-actions", () => ({
  useAccountActions: () => ({ deleteAccount: vi.fn() }),
}));

describe("DeleteAccountSection", () => {
  it("opens the confirmation that asks for the email address", async () => {
    render(<DeleteAccountSection email="ryoma@example.com" />);
    await userEvent.click(
      screen.getByRole("button", { name: "アカウントを削除" }),
    );
    expect(
      await screen.findByRole("alertdialog", {
        name: "アカウントを削除しますか？",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(/メールアドレス（ryoma@example.com）を入力/),
    ).toBeInTheDocument();
  });
});
