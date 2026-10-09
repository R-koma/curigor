import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MobileTabBar } from "@/components/layout/mobile-tab-bar";

const mocks = vi.hoisted(() => ({
  pathname: "/dashboard",
  navbarCenter: null as ReactNode,
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

describe("MobileTabBar", () => {
  it("lists the four destinations with visible labels", () => {
    mocks.navbarCenter = null;
    render(<MobileTabBar />);
    const nav = screen.getByRole("navigation", { name: "主なページ" });
    const links = nav.querySelectorAll("a");
    expect([...links].map((a) => a.getAttribute("href"))).toEqual([
      "/dashboard",
      "/learn",
      "/notes",
      "/collections",
    ]);
    expect(nav).toHaveTextContent("復習");
    expect(nav).toHaveTextContent("新規");
    expect(nav).toHaveTextContent("履歴");
    expect(nav).toHaveTextContent("まとめ");
  });

  it("marks the current page, including nested routes", () => {
    mocks.navbarCenter = null;
    mocks.pathname = "/notes/abc";
    render(<MobileTabBar />);
    expect(screen.getByRole("link", { name: "履歴" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "復習" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("is not rendered while a session owns the header slot", () => {
    mocks.navbarCenter = <span>セッション</span>;
    const { container } = render(<MobileTabBar />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is hidden on wide screens and leaves room for the home bar", () => {
    mocks.navbarCenter = null;
    render(<MobileTabBar />);
    const nav = screen.getByRole("navigation", { name: "主なページ" });
    expect(nav.className).toContain("md:hidden");
    expect(nav.className).toContain("pb-[env(safe-area-inset-bottom)]");
  });

  it("puts a pill behind the current tab's icon and keeps every label", () => {
    mocks.navbarCenter = null;
    mocks.pathname = "/learn";
    render(<MobileTabBar />);
    const current = screen.getByRole("link", { name: "新規" });
    const other = screen.getByRole("link", { name: "履歴" });
    expect(
      current.querySelector('[data-slot="tab-indicator"]')?.className,
    ).toContain("bg-muted");
    expect(
      other.querySelector('[data-slot="tab-indicator"]')?.className,
    ).not.toContain("bg-muted");
    expect(current.className).toContain("font-semibold");
    expect(other).toHaveTextContent("履歴");
  });
});
