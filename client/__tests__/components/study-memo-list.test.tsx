import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StudyMemoList } from "@/components/study-memos/study-memo-list";
import type { StudyMemoSummary } from "@/lib/study-memos";

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

function memo(id: string, topic: string): StudyMemoSummary {
  return {
    id,
    topic,
    source: "",
    created_at: "2026-10-13T00:00:00Z",
    handed_over: false,
  };
}

describe("StudyMemoList", () => {
  it("renders nothing when there is no memo", () => {
    const { container } = render(<StudyMemoList memos={[]} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("links each memo to its page", () => {
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);

    expect(screen.getByRole("link", { name: /二分探索/ })).toHaveAttribute(
      "href",
      "/study-memos/m1",
    );
  });

  it("shows only the three newest memos", () => {
    render(
      <StudyMemoList
        memos={[
          memo("m1", "一"),
          memo("m2", "二"),
          memo("m3", "三"),
          memo("m4", "四"),
        ]}
      />,
    );

    expect(screen.getAllByRole("link")).toHaveLength(3);
    expect(screen.queryByText("四")).not.toBeInTheDocument();
  });
});
