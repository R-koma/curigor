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

  it("offers to explain each memo", () => {
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);

    expect(screen.getByRole("link", { name: "説明してみる" })).toHaveAttribute(
      "href",
      "/learn?memo=m1",
    );
  });

  it("leaves out memos that already led to a note", () => {
    render(
      <StudyMemoList
        memos={[
          { ...memo("m1", "済み"), handed_over: true },
          memo("m2", "これから"),
        ]}
      />,
    );

    expect(screen.queryByText("済み")).not.toBeInTheDocument();
    expect(screen.getByText("これから")).toBeInTheDocument();
  });

  it("renders nothing when every memo already led to a note", () => {
    const { container } = render(
      <StudyMemoList memos={[{ ...memo("m1", "済み"), handed_over: true }]} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("shows only the three newest memos that are still to explain", () => {
    render(
      <StudyMemoList
        memos={[
          memo("m1", "一"),
          { ...memo("m2", "二"), handed_over: true },
          memo("m3", "三"),
          memo("m4", "四"),
          memo("m5", "五"),
        ]}
      />,
    );

    expect(screen.getAllByRole("link", { name: "説明してみる" })).toHaveLength(
      3,
    );
    expect(screen.queryByText("五")).not.toBeInTheDocument();
  });
});
