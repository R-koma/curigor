import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "@/components/layout/sidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
  }: {
    href: string;
    children: React.ReactNode;
  }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/layout/sidebar-calendar", () => ({
  SidebarCalendar: () => null,
}));

vi.mock("@/hooks/use-sidebar-width", () => ({
  useSidebarWidth: () => ({
    width: 256,
    isResizing: false,
    startResize: vi.fn(),
  }),
}));

vi.mock("@/components/layout/sidebar-account", () => ({
  SidebarAccount: ({
    isOpen,
    onBusyChange,
  }: {
    isOpen: boolean;
    onBusyChange?: (busy: boolean) => void;
  }) => (
    <div data-testid="account" data-open={isOpen}>
      <button type="button" onClick={() => onBusyChange?.(true)}>
        メニューを開く
      </button>
      <button type="button" onClick={() => onBusyChange?.(false)}>
        メニューを閉じる
      </button>
    </div>
  ),
}));

const USER = { id: "u1", name: "Ryoma", email: "ryoma@example.com" };
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe("Sidebar while the account menu is in use", () => {
  it("stays open after the pointer leaves, then closes once the menu is dismissed", async () => {
    const { container } = render(<Sidebar user={USER} />);
    const aside = container.querySelector("aside") as HTMLElement;

    await userEvent.hover(
      screen.getByRole("button", { name: "サイドバーを開く" }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("account")).toHaveAttribute(
        "data-open",
        "true",
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "メニューを開く" }));
    fireEvent.mouseLeave(aside);
    await wait(600);
    expect(screen.getByTestId("account")).toHaveAttribute("data-open", "true");

    fireEvent.click(screen.getByRole("button", { name: "メニューを閉じる" }));
    await waitFor(
      () =>
        expect(screen.getByTestId("account")).toHaveAttribute(
          "data-open",
          "false",
        ),
      { timeout: 2000 },
    );
  });

  it("does not close after the menu is dismissed while the pointer is still over the sidebar", async () => {
    const { container } = render(<Sidebar user={USER} />);
    const aside = container.querySelector("aside") as HTMLElement;

    await userEvent.hover(
      screen.getByRole("button", { name: "サイドバーを開く" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "メニューを開く" }));
    fireEvent.mouseEnter(aside);
    fireEvent.click(screen.getByRole("button", { name: "メニューを閉じる" }));
    await wait(600);
    expect(screen.getByTestId("account")).toHaveAttribute("data-open", "true");
  });
});
