import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MobileHeader } from "@/components/layout/mobile-header";

const mocks = vi.hoisted(() => ({ navbarCenter: null as ReactNode }));

vi.mock("@/context/navbar-slot-context", () => ({
  useNavbarSlot: () => ({
    navbarCenter: mocks.navbarCenter,
    setNavbarCenter: vi.fn(),
  }),
}));

vi.mock("@/components/layout/sidebar-account", () => ({
  SidebarAccount: (props: { themeInMenu?: boolean; menuSide?: string }) => (
    <div
      data-testid="account"
      data-theme-in-menu={String(props.themeInMenu)}
      data-menu-side={props.menuSide}
    />
  ),
}));

vi.mock("@/components/layout/sidebar-calendar", () => ({
  SidebarCalendar: () => <div data-testid="sidebar-calendar" />,
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

describe("MobileHeader", () => {
  it("shows the logo, the calendar button and the account when no session owns the slot", () => {
    mocks.navbarCenter = null;
    render(<MobileHeader user={USER} />);
    expect(screen.getByRole("link", { name: /Curigor/ })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(
      screen.getByRole("button", { name: "カレンダー" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("account")).toHaveAttribute(
      "data-theme-in-menu",
      "true",
    );
    expect(screen.getByTestId("account")).toHaveAttribute(
      "data-menu-side",
      "bottom",
    );
  });

  it("opens the calendar in a dialog", async () => {
    mocks.navbarCenter = null;
    render(<MobileHeader user={USER} />);
    expect(screen.queryByTestId("sidebar-calendar")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "カレンダー" }));
    expect(
      await screen.findByRole("dialog", { name: "カレンダー" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("sidebar-calendar")).toBeInTheDocument();
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
