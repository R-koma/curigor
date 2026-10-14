import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
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

const MEMO: StudyMemo = {
  id: "m1",
  topic: "二分探索",
  source: "大学の講義資料",
  overview: [
    {
      aspect_id: "a1",
      name: "真ん中との比較",
      summary: "真ん中と比べて半分を捨てる",
      is_core: true,
    },
    {
      aspect_id: "a2",
      name: "計算量",
      summary: "",
      is_core: true,
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
  it("shows the topic, the material and that it records what the AI taught", () => {
    render(<StudyMemoView memo={MEMO} />);

    expect(
      screen.getByRole("heading", { level: 1, name: "二分探索" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/大学の講義資料/)).toBeInTheDocument();
    expect(screen.getByText(/AI に教わった内容の記録です/)).toBeInTheDocument();
  });

  it("lists the aspects to explain, core ones first, without taught marks", () => {
    render(<StudyMemoView memo={MEMO} />);

    const overview = screen.getByRole("region", { name: "全体像" });
    expect(within(overview).getByText("真ん中との比較")).toBeInTheDocument();
    expect(within(overview).queryByText("教わった")).not.toBeInTheDocument();
    expect(within(overview).queryByText("未説明")).not.toBeInTheDocument();
  });

  it("shows the glossary with readings when there is one", () => {
    render(<StudyMemoView memo={MEMO} />);

    const glossary = screen.getByRole("region", { name: "用語集" });
    expect(
      within(glossary).getByText("計算量（けいさんりょう）"),
    ).toBeInTheDocument();
    expect(within(glossary).getByText("添字")).toBeInTheDocument();
    expect(
      within(glossary).getByText("要素の位置を表す番号"),
    ).toBeInTheDocument();
  });

  it("shows questions with answers, and says when an answer could not be summarised", () => {
    render(<StudyMemoView memo={MEMO} />);

    const questions = screen.getByRole("region", { name: "疑問と回答" });
    expect(
      within(questions).getByText("半分を捨てる判断に必要だから"),
    ).toBeInTheDocument();
    expect(
      within(questions).getByText("回答の要約はありません"),
    ).toBeInTheDocument();
  });

  it("says so for empty sections", () => {
    render(
      <StudyMemoView
        memo={{ ...MEMO, glossary: [], questions: [], source: "" }}
      />,
    );

    expect(screen.getByText("用語はありません")).toBeInTheDocument();
    expect(screen.getByText("疑問はありません")).toBeInTheDocument();
    expect(screen.queryByText(/教材:/)).not.toBeInTheDocument();
  });

  it("offers to explain what was taught, starting a learning session from the memo", () => {
    render(<StudyMemoView memo={MEMO} />);

    expect(screen.getByRole("link", { name: "説明してみる" })).toHaveAttribute(
      "href",
      "/learn?memo=m1",
    );
  });
});
