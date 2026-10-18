import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { NoteStudyMemos } from "@/components/notes/note-study-memos";
import type { NoteStudyMemo } from "@/lib/study-memos";

const MEMOS: NoteStudyMemo[] = [
  {
    id: "m2",
    topic: "再帰と反復",
    created_at: "2026-06-05T00:00:00Z",
    feedback_id: "f2",
    improvement_index: 0,
    improvement: "再帰の終了条件",
    aspect_id: null,
  },
  {
    id: "m1",
    topic: "計算量",
    created_at: "2026-06-01T00:00:00Z",
    feedback_id: null,
    improvement_index: null,
    improvement: null,
    aspect_id: null,
  },
];

describe("NoteStudyMemos", () => {
  it("lists memos with links", () => {
    render(<NoteStudyMemos memos={MEMOS} />);
    expect(
      screen.getByRole("heading", { name: "このノートから作った学習メモ" }),
    ).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    const first = within(items[0]).getByRole("link", { name: /再帰と反復/ });
    expect(first).toHaveAttribute("href", "/study-memos/m2");
    expect(within(items[0]).getByText("2026年6月5日")).toBeInTheDocument();
    expect(within(items[0]).getByText("再帰の終了条件")).toBeInTheDocument();
  });
});
