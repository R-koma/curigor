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
  it("offers to learn from the AI when there is no memo", () => {
    render(<StudyMemoList memos={[]} />);

    expect(screen.getByText("学習メモはありません。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "AI に教わる" })).toHaveAttribute(
      "href",
      "/learn?mode=explore",
    );
  });

  it("links each memo to its page", () => {
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);

    expect(screen.getByRole("link", { name: /二分探索/ })).toHaveAttribute(
      "href",
      "/study-memos/m1",
    );
  });

  it("shows the source next to the date when there is one", () => {
    render(
      <StudyMemoList
        memos={[{ ...memo("m1", "二分探索"), source: "講義資料" }]}
      />,
    );

    expect(screen.getByRole("link", { name: /二分探索/ })).toHaveTextContent(
      "講義資料",
    );
  });

  it("offers to explain a memo that has not led to a note yet", () => {
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);

    expect(screen.getByRole("link", { name: "説明してみる" })).toHaveAttribute(
      "href",
      "/learn?memo=m1",
    );
    expect(screen.queryByText("説明済み")).not.toBeInTheDocument();
  });

  it("keeps memos that already led to a note and marks them as explained", () => {
    render(
      <StudyMemoList memos={[{ ...memo("m1", "済み"), handed_over: true }]} />,
    );

    expect(screen.getByRole("link", { name: /済み/ })).toHaveAttribute(
      "href",
      "/study-memos/m1",
    );
    expect(screen.getByText("説明済み")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "説明してみる" }),
    ).not.toBeInTheDocument();
  });

  it("lists every memo in the order given", () => {
    const topics = ["一", "二", "三", "四", "五"];
    render(<StudyMemoList memos={topics.map((t, i) => memo(`m${i}`, t))} />);

    expect(
      screen
        .getAllByRole("link", { name: /^[一二三四五]/ })
        .map((a) => a.textContent?.charAt(0)),
    ).toEqual(topics);
  });
});
