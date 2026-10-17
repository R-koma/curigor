import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
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
    aspects: [],
    glossary_count: 0,
    question_count: 0,
  };
}

describe("StudyMemoList", () => {
  it("offers to understand a topic with the AI when there is no memo", () => {
    render(<StudyMemoList memos={[]} />);

    expect(screen.getByText("学習メモはありません。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "理解する" })).toHaveAttribute(
      "href",
      "/learn?mode=explore",
    );
  });

  it("links each memo to its page", () => {
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);

    expect(screen.getByRole("link", { name: "二分探索" })).toHaveAttribute(
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

    expect(screen.getByText(/講義資料/)).toBeInTheDocument();
  });

  it("puts the core aspects first and folds the rest after three", () => {
    render(
      <StudyMemoList
        memos={[
          {
            ...memo("m1", "二分探索"),
            aspects: [
              { name: "計算量", is_core: false },
              { name: "半分にする", is_core: true },
              { name: "前提", is_core: false },
              { name: "比較", is_core: true },
              { name: "応用", is_core: false },
            ],
          },
        ]}
      />,
    );

    const chips = within(screen.getByRole("list", { name: "観点" }))
      .getAllByRole("listitem")
      .map((li) => li.textContent);
    expect(chips).toEqual(["半分にする", "比較", "計算量", "+2"]);
    expect(screen.getByText("半分にする").className).toContain("bg-brand-soft");
    expect(screen.getByText("計算量").className).not.toContain("bg-brand-soft");
  });

  it("leaves out the aspect row when the memo has no aspect", () => {
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);

    expect(
      screen.queryByRole("list", { name: "観点" }),
    ).not.toBeInTheDocument();
  });

  it("counts the terms and the questions", () => {
    render(
      <StudyMemoList
        memos={[
          { ...memo("m1", "二分探索"), glossary_count: 6, question_count: 4 },
        ]}
      />,
    );

    expect(screen.getByText(/用語/)).toHaveTextContent("用語 6");
    expect(screen.getByText(/疑問/)).toHaveTextContent("疑問 4");
  });

  it("offers to explain a memo that has not led to a note yet", () => {
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);

    expect(screen.getByText("説明待ち")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "説明してみる" })).toHaveAttribute(
      "href",
      "/learn?memo=m1",
    );
  });

  it("keeps memos that already led to a note and marks them as explained", () => {
    render(
      <StudyMemoList memos={[{ ...memo("m1", "済み"), handed_over: true }]} />,
    );

    expect(screen.getByRole("link", { name: "済み" })).toHaveAttribute(
      "href",
      "/study-memos/m1",
    );
    expect(screen.getByText("説明済み")).toBeInTheDocument();
    expect(screen.queryByText("説明待ち")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "説明してみる" }),
    ).not.toBeInTheDocument();
  });

  it("lists every memo in the order given", () => {
    const topics = ["一", "二", "三", "四", "五"];
    render(<StudyMemoList memos={topics.map((t, i) => memo(`m${i}`, t))} />);

    expect(
      screen
        .getAllByRole("link", { name: /^[一二三四五]$/ })
        .map((a) => a.textContent),
    ).toEqual(topics);
  });
});
