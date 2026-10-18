import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StudyMemoView } from "@/components/study-memos/study-memo-view";
import type { StudyMemo } from "@/lib/study-memos";

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

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));

const MEMO: StudyMemo = {
  id: "m1",
  topic: "二分探索",
  source: "大学の講義資料",
  summary: "並んだ配列で真ん中と比べ、探す範囲を半分ずつ狭める方法を教わった。",
  overview: [
    {
      aspect_id: "a1",
      name: "真ん中との比較",
      summary: "真ん中と比べて半分を捨てる",
      is_core: true,
      question_indices: [0],
      term_indices: [0],
    },
    {
      aspect_id: "a2",
      name: "計算量の見積もり",
      summary: "",
      is_core: false,
      question_indices: [],
      term_indices: [],
    },
  ],
  glossary: [
    {
      term: "計算量",
      reading: "けいさんりょう",
      meaning: "処理にかかる手間の目安",
    },
    { term: "添字", reading: "", meaning: "要素の位置を表す番号" },
  ],
  questions: [
    {
      question: "なぜ並んでいる必要があるのか",
      answer: "半分を捨てる判断に必要だから",
    },
    { question: "途中で値が変わったら", answer: "" },
  ],
  created_at: "2026-10-13T00:00:00Z",
};

describe("StudyMemoView", () => {
  it("shows the topic, the material and the memo summary without a note on what the AI taught", () => {
    render(<StudyMemoView memo={MEMO} />);

    expect(
      screen.getByRole("heading", { level: 1, name: "二分探索" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        `${new Date(MEMO.created_at).toLocaleDateString("ja-JP")} · 大学の講義資料`,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/探す範囲を半分ずつ狭める/)).toBeInTheDocument();
    expect(
      screen.queryByText(/AI に教わった内容の記録です/),
    ).not.toBeInTheDocument();
  });

  it("leaves out the material and the summary when there are none", () => {
    render(<StudyMemoView memo={{ ...MEMO, source: "", summary: "" }} />);

    expect(
      screen.getByText(new Date(MEMO.created_at).toLocaleDateString("ja-JP")),
    ).toBeInTheDocument();
    expect(screen.queryByText(/ · /)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/探す範囲を半分ずつ狭める/),
    ).not.toBeInTheDocument();
  });

  it("shows each aspect with content and its one-line summary, and leaves out empty aspects", () => {
    render(<StudyMemoView memo={MEMO} />);

    expect(screen.getByText("真ん中との比較")).toBeInTheDocument();
    expect(screen.getByText("真ん中と比べて半分を捨てる")).toBeInTheDocument();
    expect(
      screen.getByText("観点に入らなかった疑問と用語"),
    ).toBeInTheDocument();
    expect(screen.queryByText("計算量の見積もり")).not.toBeInTheDocument();
  });

  it("opens only the first aspect at first", () => {
    render(<StudyMemoView memo={MEMO} />);

    expect(
      screen.getByRole("button", { name: "真ん中との比較を閉じる" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("button", {
        name: "観点に入らなかった疑問と用語を開く",
      }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.getByText("なぜ並んでいる必要があるのか"),
    ).toBeInTheDocument();
    expect(screen.queryByText("途中で値が変わったら")).not.toBeInTheDocument();
  });

  it("opens an answer or a meaning by pressing anywhere on its card", async () => {
    const user = userEvent.setup();
    render(<StudyMemoView memo={MEMO} />);

    expect(
      screen.queryByText("半分を捨てる判断に必要だから"),
    ).not.toBeInTheDocument();
    await user.click(screen.getByText("なぜ並んでいる必要があるのか"));
    expect(
      screen.getByText("半分を捨てる判断に必要だから"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "なぜ並んでいる必要があるのか" }),
    ).toHaveAttribute("aria-expanded", "true");

    expect(screen.getByText("けいさんりょう")).toBeInTheDocument();
    expect(
      screen.queryByText("処理にかかる手間の目安"),
    ).not.toBeInTheDocument();
    await user.click(screen.getByText("けいさんりょう"));
    expect(screen.getByText("処理にかかる手間の目安")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "計算量けいさんりょう" }),
    ).toHaveAttribute("aria-expanded", "true");

    await user.click(
      screen.getByRole("button", { name: "なぜ並んでいる必要があるのか" }),
    );
    expect(
      screen.queryByText("半分を捨てる判断に必要だから"),
    ).not.toBeInTheDocument();
  });

  it("points aria-controls at the revealed panel", async () => {
    const user = userEvent.setup();
    render(<StudyMemoView memo={MEMO} />);

    const card = screen.getByRole("button", {
      name: "なぜ並んでいる必要があるのか",
    });
    await user.click(card);
    const panel = document.getElementById(card.getAttribute("aria-controls")!);
    expect(panel).toHaveTextContent("半分を捨てる判断に必要だから");

    const aspect = screen.getByRole("button", {
      name: "真ん中との比較を閉じる",
    });
    const aspectPanel = document.getElementById(
      aspect.getAttribute("aria-controls")!,
    );
    expect(aspectPanel).toContainElement(card);
  });

  it("shows that an answer has no summary when it is empty", async () => {
    const user = userEvent.setup();
    render(<StudyMemoView memo={MEMO} />);

    await user.click(
      screen.getByRole("button", {
        name: "観点に入らなかった疑問と用語を開く",
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "途中で値が変わったら" }),
    );
    expect(screen.getByText("回答の要約はありません")).toBeInTheDocument();
  });

  it("puts unassigned questions and terms under their own group", async () => {
    const user = userEvent.setup();
    render(<StudyMemoView memo={MEMO} />);

    expect(screen.queryByText("添字")).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", {
        name: "観点に入らなかった疑問と用語を開く",
      }),
    );
    expect(screen.getByText("途中で値が変わったら")).toBeInTheDocument();
    expect(screen.getByText("添字")).toBeInTheDocument();
  });

  it("has no toggle to show all answers and no counts", () => {
    render(<StudyMemoView memo={MEMO} />);

    expect(screen.queryByText(/全部表示/)).not.toBeInTheDocument();
    expect(screen.queryByText(/答えを見る|意味を見る/)).not.toBeInTheDocument();
    expect(screen.queryByText(/疑問 \d/)).not.toBeInTheDocument();
    expect(screen.queryByText(/観点 \d/)).not.toBeInTheDocument();
  });

  it("labels the memo summary and offers the actions menu", () => {
    render(<StudyMemoView memo={MEMO} />);

    expect(screen.getByRole("region", { name: "要約" })).toHaveTextContent(
      "探す範囲を半分ずつ狭める",
    );
    expect(
      screen.getByRole("button", { name: "その他の操作" }),
    ).toBeInTheDocument();
  });

  it("links 説明してみる to the learn page with the memo", () => {
    render(<StudyMemoView memo={MEMO} />);

    expect(screen.getByRole("link", { name: "説明してみる" })).toHaveAttribute(
      "href",
      "/learn?memo=m1",
    );
  });

  it("says there are no questions or terms when the memo is empty", () => {
    render(<StudyMemoView memo={{ ...MEMO, glossary: [], questions: [] }} />);

    expect(screen.getByText("まだ疑問や用語はありません")).toBeInTheDocument();
    expect(
      screen.queryByText("観点に入らなかった疑問と用語"),
    ).not.toBeInTheDocument();
  });

  it("renders formulas and code in summaries, meanings and answers", async () => {
    const user = userEvent.setup();
    const memo: StudyMemo = {
      ...MEMO,
      overview: [{ ...MEMO.overview[0], summary: "比較は $O(\\log n)$ 回" }],
      glossary: [
        { term: "中央", reading: "", meaning: "`mid = (lo + hi) // 2` の位置" },
      ],
      questions: [{ question: "比較の回数は", answer: "最大 $\\log_2 n$ 回" }],
    };
    const { container } = render(<StudyMemoView memo={memo} />);

    await user.click(screen.getByRole("button", { name: "比較の回数は" }));
    await user.click(screen.getByRole("button", { name: "中央" }));
    expect(container.querySelectorAll(".katex")).toHaveLength(2);
    expect(screen.getByText("mid = (lo + hi) // 2").tagName).toBe("CODE");
  });
});
