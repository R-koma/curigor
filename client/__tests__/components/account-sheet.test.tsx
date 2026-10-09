import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccountSheet } from "@/components/layout/account-sheet";

const mocks = vi.hoisted(() => ({
  theme: "system",
  setTheme: vi.fn(),
  resetHints: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: mocks.theme, setTheme: mocks.setTheme }),
}));

vi.mock("@/hooks/use-account-actions", () => ({
  useAccountActions: () => ({
    resetHints: mocks.resetHints,
    signOut: mocks.signOut,
  }),
}));

vi.mock("@/components/layout/avatar-settings-modal", () => ({
  AvatarSettingsModal: ({ open }: { open: boolean }) =>
    open ? <div role="dialog" aria-label="写真の設定" /> : null,
}));

const USER = { id: "u1", name: "Ryoma", email: "r@example.com", image: null };

function renderSheet() {
  render(
    <AccountSheet
      user={USER}
      avatarUrl={null}
      onAvatarChange={vi.fn()}
      open
      onOpenChange={vi.fn()}
    />,
  );
  return screen.getByRole("dialog", { name: "アカウント" });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.theme = "system";
});

describe("AccountSheet", () => {
  it("shows who is signed in", () => {
    const sheet = renderSheet();
    expect(within(sheet).getByText("Ryoma")).toBeInTheDocument();
    expect(within(sheet).getByText("r@example.com")).toBeInTheDocument();
  });

  it("offers light, dark and automatic themes and marks the current one", async () => {
    const sheet = renderSheet();
    const group = within(sheet).getByRole("group", { name: "テーマ" });
    expect(within(group).getByRole("button", { name: "自動" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(
      within(group).getByRole("button", { name: "ダーク" }),
    ).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(
      within(group).getByRole("button", { name: "ダーク" }),
    );
    expect(mocks.setTheme).toHaveBeenCalledWith("dark");
  });

  it("changes the photo from the avatar", async () => {
    const sheet = renderSheet();
    await userEvent.click(
      within(sheet).getByRole("button", { name: "写真を変更" }),
    );
    expect(
      await screen.findByRole("dialog", { name: "写真の設定" }),
    ).toBeInTheDocument();
  });

  it("resets the hints and signs out with large touch targets", async () => {
    const sheet = renderSheet();
    const hints = within(sheet).getByRole("button", {
      name: "ヒントをもう一度表示する",
    });
    const signOut = within(sheet).getByRole("button", { name: "ログアウト" });
    expect(hints.className).toContain("min-h-11");
    expect(signOut.className).toContain("min-h-11");
    expect(signOut.className).toContain("text-destructive");
    await userEvent.click(hints);
    expect(mocks.resetHints).toHaveBeenCalledTimes(1);
    await userEvent.click(signOut);
    expect(mocks.signOut).toHaveBeenCalledTimes(1);
  });

  it("keeps sign-out apart from the other rows", () => {
    const sheet = renderSheet();
    const signOut = within(sheet).getByRole("button", { name: "ログアウト" });
    expect(signOut.closest("[data-slot=account-danger]")).not.toBeNull();
    expect(
      within(sheet)
        .getByRole("button", { name: "ヒントをもう一度表示する" })
        .closest("[data-slot=account-danger]"),
    ).toBeNull();
  });
});
