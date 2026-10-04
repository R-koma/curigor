import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SidebarAccount } from "@/components/layout/sidebar-account";

const mocks = vi.hoisted(() => ({
  setTheme: vi.fn(),
  push: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "light", setTheme: mocks.setTheme }),
}));

vi.mock("@/lib/auth-client", () => ({
  authClient: { signOut: mocks.signOut },
}));

vi.mock("@/components/layout/avatar-settings-modal", () => ({
  AvatarSettingsModal: () => null,
}));

const USER = {
  id: "u1",
  name: "Ryoma",
  email: "ryoma@example.com",
  image: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SidebarAccount", () => {
  it("lays out the avatar, the name and the theme toggle from left to right when open", () => {
    render(<SidebarAccount user={USER} isOpen />);
    const avatar = screen.getByText("R");
    const name = screen.getByText("Ryoma");
    const toggle = screen.getByRole("button", { name: "テーマ切り替え" });
    const follows = (a: Node, b: Node) =>
      Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    expect(follows(avatar, name)).toBe(true);
    expect(follows(name, toggle)).toBe(true);
  });

  it("switches the theme from the toggle", async () => {
    render(<SidebarAccount user={USER} isOpen />);
    await userEvent.click(
      screen.getByRole("button", { name: "テーマ切り替え" }),
    );
    expect(mocks.setTheme).toHaveBeenCalledWith("dark");
  });

  it("shows only the avatar when the sidebar is collapsed", () => {
    render(<SidebarAccount user={USER} isOpen={false} />);
    expect(screen.getByText("R")).toBeInTheDocument();
    expect(screen.queryByText("Ryoma")).toBeNull();
    expect(screen.queryByRole("button", { name: "テーマ切り替え" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "アカウントメニュー" }),
    ).toBeInTheDocument();
  });

  it("opens the account menu and signs out", async () => {
    render(<SidebarAccount user={USER} isOpen />);
    await userEvent.click(
      screen.getByRole("button", { name: "アカウントメニュー" }),
    );
    expect(await screen.findByText("ryoma@example.com")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("menuitem", { name: "ログアウト" }));
    expect(mocks.signOut).toHaveBeenCalledTimes(1);
  });
});
