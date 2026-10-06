import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
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
  AvatarSettingsModal: ({ open }: { open: boolean }) =>
    open ? <div role="dialog">写真の設定</div> : null,
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

  it("reports when the account menu is open so the sidebar can stay open", async () => {
    const onBusyChange = vi.fn();
    render(<SidebarAccount user={USER} isOpen onBusyChange={onBusyChange} />);
    await userEvent.click(
      screen.getByRole("button", { name: "アカウントメニュー" }),
    );
    expect(onBusyChange).toHaveBeenLastCalledWith(true);
    await userEvent.keyboard("{Escape}");
    expect(onBusyChange).toHaveBeenLastCalledWith(false);
  });

  it("draws no focus outline or ring on its controls", async () => {
    render(<SidebarAccount user={USER} isOpen />);
    const trigger = screen.getByRole("button", { name: "アカウントメニュー" });
    const toggle = screen.getByRole("button", { name: "テーマ切り替え" });
    expect(trigger.className).toContain("outline-none");
    expect(trigger.className).not.toMatch(/focus-visible:ring-[1-9]/);
    expect(toggle.className).toContain("focus-visible:ring-0");
    expect(toggle.className).toContain("outline-none");

    await userEvent.click(trigger);
    const photo = await screen.findByRole("menuitem", { name: "写真を変更" });
    expect(photo.className).not.toMatch(/focus-visible:(ring|outline)/);
  });

  it("marks the row as a menu with a chevron next to the name, only when open", () => {
    const { rerender } = render(<SidebarAccount user={USER} isOpen />);
    const trigger = screen.getByRole("button", { name: "アカウントメニュー" });
    expect(trigger.querySelector("svg.lucide-chevron-up")).not.toBeNull();
    const name = within(trigger).getByText("Ryoma");
    const chevron = trigger.querySelector("svg.lucide-chevron-up")!;
    expect(
      Boolean(
        name.compareDocumentPosition(chevron) &
        Node.DOCUMENT_POSITION_FOLLOWING,
      ),
    ).toBe(true);

    rerender(<SidebarAccount user={USER} isOpen={false} />);
    expect(
      screen
        .getByRole("button", { name: "アカウントメニュー" })
        .querySelector("svg.lucide-chevron-up"),
    ).toBeNull();
  });

  it("does not repeat the avatar and name inside the menu; it shows the email, a photo item and log out", async () => {
    render(<SidebarAccount user={USER} isOpen />);
    await userEvent.click(
      screen.getByRole("button", { name: "アカウントメニュー" }),
    );
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByText("ryoma@example.com")).toBeInTheDocument();
    expect(within(menu).queryByText("Ryoma")).toBeNull();
    expect(within(menu).queryByText("R")).toBeNull();
    expect(
      within(menu)
        .getAllByRole("menuitem")
        .map((item) => item.textContent?.trim()),
    ).toEqual(["写真を変更", "ログアウト"]);
  });

  it("opens the photo dialog from the photo item and closes the menu", async () => {
    render(<SidebarAccount user={USER} isOpen />);
    await userEvent.click(
      screen.getByRole("button", { name: "アカウントメニュー" }),
    );
    await userEvent.click(
      await screen.findByRole("menuitem", { name: "写真を変更" }),
    );
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("lines up with the nav tabs: full-width row, same side padding on the button", () => {
    render(<SidebarAccount user={USER} isOpen />);
    const trigger = screen.getByRole("button", { name: "アカウントメニュー" });
    const row = trigger.parentElement as HTMLElement;
    expect(row).toHaveClass("w-full");
    expect(row).not.toHaveClass("max-w-[280px]");
    expect(row.style.paddingInline).toBe("");
    expect(trigger).toHaveClass("px-2");
  });

  it("stays a compact centered avatar that fits the narrow rail when collapsed", () => {
    render(<SidebarAccount user={USER} isOpen={false} />);
    const trigger = screen.getByRole("button", { name: "アカウントメニュー" });
    const row = trigger.parentElement as HTMLElement;
    expect(row).not.toHaveClass("max-w-[280px]");
    expect(row.style.paddingInline).toBe("");
    expect(trigger).toHaveClass("p-1");
    expect(trigger).not.toHaveClass("px-2");
  });

  it("falls back to U when the name is empty", () => {
    render(<SidebarAccount user={{ ...USER, name: "" }} isOpen={false} />);
    expect(screen.getByText("U")).toBeInTheDocument();
  });

  it("shows every menu text in one color, the theme foreground", async () => {
    render(<SidebarAccount user={USER} isOpen />);
    await userEvent.click(
      screen.getByRole("button", { name: "アカウントメニュー" }),
    );
    const menu = await screen.findByRole("menu");
    const texts = [
      within(menu).getByText("ryoma@example.com"),
      ...within(menu).getAllByRole("menuitem"),
    ];
    expect(texts).toHaveLength(3);
    for (const element of texts) {
      expect(element).toHaveClass("text-foreground");
      expect(element.className).not.toContain("text-muted-foreground");
    }
  });
});
