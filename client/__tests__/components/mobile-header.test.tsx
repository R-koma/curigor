import { describe, it, expect, vi } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import Link from "next/link";
import { MobileHeader } from "@/components/layout/mobile-header";
import { setMediaQuery } from "@/__tests__/stubs/match-media";

const mocks = vi.hoisted(() => ({
  navbarCenter: null as ReactNode,
  pathname: "/dashboard",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
}));

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

vi.mock("@/components/layout/drawer-recent", () => ({
  DrawerRecent: () => <div data-testid="drawer-recent" />,
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
  it("shows the menu button and the page title in one row without a divider or the logo", () => {
    mocks.navbarCenter = null;
    mocks.pathname = "/dashboard";
    render(<MobileHeader user={USER} />);
    const header = screen.getByRole("banner");
    expect(
      screen.getByRole("button", { name: "メニュー" }),
    ).toBeInTheDocument();
    expect(header).toHaveTextContent("今日の復習");
    expect(header.className).not.toContain("border-b");
    expect(screen.queryByRole("link", { name: /Curigor/ })).toBeNull();
    expect(header.querySelector('[data-testid="account"]')).toBeNull();
  });

  it("shows no title on pages without one", () => {
    mocks.navbarCenter = null;
    mocks.pathname = "/notes/abc";
    render(<MobileHeader user={USER} />);
    expect(screen.getByRole("banner").textContent).toBe("");
  });

  it("opens a drawer with the logo on top, the recent items and the expanded account", async () => {
    mocks.navbarCenter = null;
    mocks.pathname = "/dashboard";
    render(<MobileHeader user={USER} />);
    const drawer = await openMenu();
    expect(
      within(drawer).getByRole("link", { name: /Curigor/ }),
    ).toHaveAttribute("href", "/dashboard");
    expect(within(drawer).getByTestId("drawer-recent")).toBeInTheDocument();
    expect(screen.queryByTestId("sidebar-calendar")).toBeNull();
    const accounts = screen.getAllByTestId("account");
    expect(accounts).toHaveLength(1);
    expect(accounts[0]).toHaveAttribute("data-is-open", "true");
  });

  it("opens the calendar full screen and closes everything when a note in it is followed", async () => {
    mocks.navbarCenter = null;
    mocks.pathname = "/dashboard";
    render(<MobileHeader user={USER} />);
    const drawer = await openMenu();
    await userEvent.click(
      within(drawer).getByRole("button", { name: "カレンダー" }),
    );
    const calendar = await screen.findByRole("dialog", { name: "カレンダー" });
    expect(calendar.className).toContain("h-dvh");
    await userEvent.click(
      within(calendar).getByRole("link", { name: "選んだ日のノート" }),
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

  it("closes the drawer when the route changes without a link click, such as the back button", async () => {
    mocks.navbarCenter = null;
    mocks.pathname = "/dashboard";
    const { rerender } = render(<MobileHeader user={USER} />);
    await openMenu();
    mocks.pathname = "/notes";
    rerender(<MobileHeader user={USER} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("closes the drawer when the viewport grows to the wide layout", async () => {
    mocks.navbarCenter = null;
    mocks.pathname = "/dashboard";
    render(<MobileHeader user={USER} />);
    await openMenu();
    act(() => setMediaQuery("(min-width: 48rem)", true));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("gives the full-screen calendar a 44px close button clear of the notch", async () => {
    mocks.navbarCenter = null;
    mocks.pathname = "/dashboard";
    render(<MobileHeader user={USER} />);
    const drawer = await openMenu();
    await userEvent.click(
      within(drawer).getByRole("button", { name: "カレンダー" }),
    );
    const calendar = await screen.findByRole("dialog", { name: "カレンダー" });
    const closes = within(calendar).getAllByRole("button", { name: "閉じる" });
    expect(closes).toHaveLength(1);
    expect(closes[0].className).toContain("size-11");
    expect(closes[0].className).toContain("safe-area-inset-top");
    await userEvent.click(closes[0]);
    expect(screen.queryByRole("dialog", { name: "カレンダー" })).toBeNull();
    expect(
      screen.getByRole("dialog", { name: "メニュー" }),
    ).toBeInTheDocument();
  });
});
