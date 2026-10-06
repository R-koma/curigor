import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const useSessionMock = vi.fn();

vi.mock("@/lib/auth-client", () => ({
  authClient: {
    useSession: () => useSessionMock(),
  },
}));

import LandingAuthCta from "@/components/landing/landing-auth-cta";

describe("LandingAuthCta", () => {
  it("shows sign-in links when logged out", () => {
    useSessionMock.mockReturnValue({ data: null, isPending: false });
    render(<LandingAuthCta />);

    expect(screen.getByRole("link", { name: "ログイン" })).toHaveAttribute(
      "href",
      "/sign-in",
    );
    expect(screen.getByRole("link", { name: "無料で始める" })).toHaveAttribute(
      "href",
      "/sign-in",
    );
    expect(screen.queryByRole("link", { name: "ダッシュボードへ" })).toBeNull();
  });

  it("shows dashboard link when logged in", () => {
    useSessionMock.mockReturnValue({
      data: { user: { id: "u1" } },
      isPending: false,
    });
    render(<LandingAuthCta />);

    expect(
      screen.getByRole("link", { name: "ダッシュボードへ" }),
    ).toHaveAttribute("href", "/dashboard");
    expect(screen.queryByRole("link", { name: "無料で始める" })).toBeNull();
  });

  it("shows logged-out CTAs while pending to match the prerendered output", () => {
    useSessionMock.mockReturnValue({ data: null, isPending: true });
    render(<LandingAuthCta />);

    expect(screen.getByRole("link", { name: "ログイン" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "無料で始める" }),
    ).toBeInTheDocument();
  });
});
