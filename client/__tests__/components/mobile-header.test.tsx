import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import Link from "next/link";
import { MobileHeader } from "@/components/layout/mobile-header";

const mocks = vi.hoisted(() => ({ navbarCenter: null as ReactNode }));

vi.mock("@/context/navbar-slot-context", () => ({
  useNavbarSlot: () => ({
    navbarCenter: mocks.navbarCenter,
    setNavbarCenter: vi.fn(),
  }),
}));

vi.mock("@/components/layout/sidebar-account", () => ({
  SidebarAccount: (props: { isOpen: boolean; themeInMenu?: boolean }) => (
    <div
      data-testid="account"
      data-is-open={String(props.isOpen)}
      data-theme-in-menu={String(props.themeInMenu)}
    />
  ),
}));

vi.mock("@/components/layout/sidebar-calendar", () => ({
  SidebarCalendar: () => (
    <div data-testid="sidebar-calendar">
      <Link href="/notes/n1">選んだ日のノート</Link>
    </div>
  ),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: React.ComponentProps<"a"> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const USER = { id: "u1", name: "Ryoma", email: "r@example.com", image: null };

async function openMenu() {
  await userEvent.click(screen.getByRole("button", { name: "メニュー" }));
  return screen.findByRole("dialog", { name: "メニュー" });
}

describe("MobileHeader", () => {
  it("shows the menu button and the logo, and keeps the calendar and the account out of the header", () => {
    mocks.navbarCenter = null;
    render(<MobileHeader user={USER} />);
    const header = screen.getByRole("banner");
    expect(
      screen.getByRole("button", { name: "メニュー" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Curigor/ })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(header.querySelector('[data-testid="account"]')).toBeNull();
    expect(screen.queryByRole("button", { name: "カレンダー" })).toBeNull();
  });

  it("opens a drawer with the calendar and the expanded account", async () => {
    mocks.navbarCenter = null;
    render(<MobileHeader user={USER} />);
    expect(screen.queryByTestId("sidebar-calendar")).toBeNull();
    await openMenu();
    expect(screen.getByTestId("sidebar-calendar")).toBeInTheDocument();
    const accounts = screen.getAllByTestId("account");
    expect(accounts).toHaveLength(1);
    expect(accounts[0]).toHaveAttribute("data-is-open", "true");
    expect(accounts[0]).toHaveAttribute("data-theme-in-menu", "undefined");
  });

  it("closes the drawer when a link inside it is followed", async () => {
    mocks.navbarCenter = null;
    render(<MobileHeader user={USER} />);
    await openMenu();
    await userEvent.click(
      screen.getByRole("link", { name: "選んだ日のノート" }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders nothing while a session owns the header slot, so the slot is mounted once", () => {
    mocks.navbarCenter = <span>トピック名</span>;
    const { container } = render(<MobileHeader user={USER} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is hidden on wide screens", () => {
    mocks.navbarCenter = null;
    render(<MobileHeader user={USER} />);
    expect(screen.getByRole("banner").className).toContain("md:hidden");
  });
});
