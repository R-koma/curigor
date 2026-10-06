import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/auth-client", () => ({
  authClient: {
    useSession: () => ({ data: null, isPending: false }),
  },
}));

import Home from "@/app/page";

describe("landing page", () => {
  it("renders a single h1 hero headline", () => {
    render(<Home />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("sends every auth link to the single sign-in page", () => {
    const { container } = render(<Home />);
    expect(container.querySelectorAll('a[href="/sign-up"]')).toHaveLength(0);
    expect(
      container.querySelectorAll('a[href="/sign-in"]').length,
    ).toBeGreaterThan(0);
  });

  it("shows the core feature headings", () => {
    render(<Home />);
    expect(screen.getByText("ノート自動生成")).toBeInTheDocument();
    expect(screen.getByText("忘却曲線ベースの復習")).toBeInTheDocument();
    expect(screen.getByText("AI フィードバック")).toBeInTheDocument();
  });
});
