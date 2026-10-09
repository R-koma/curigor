import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageHeading } from "@/components/layout/page-heading";

describe("PageHeading", () => {
  it("names the page and adds a quiet line about where things stand", () => {
    render(<PageHeading title="学習履歴" description="ノート 24 件" />);
    const heading = screen.getByRole("heading", { level: 1, name: "学習履歴" });
    expect(heading.className).toContain("tracking-tight");
    const note = screen.getByText("ノート 24 件");
    expect(note.className).toContain("text-muted-foreground");
  });

  it("drops the decorative side bar", () => {
    const { container } = render(<PageHeading title="まとめ" />);
    expect(container.innerHTML).not.toContain("border-l-4");
  });

  it("keeps the heading for screen readers only on phones", () => {
    const { container } = render(<PageHeading title="まとめ" />);
    expect((container.firstChild as HTMLElement).className).toContain(
      "max-md:sr-only",
    );
  });
});
