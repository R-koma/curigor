import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CollectionSynthesis } from "@/components/collections/collection-synthesis";
import type { Synthesis } from "@/lib/collections";

const fetchAPI = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchAPI: (...args: unknown[]) => fetchAPI(...args),
}));

const toastError = vi.fn();
vi.mock("sonner", () => ({ toast: { error: (m: string) => toastError(m) } }));

const SYNTHESIS: Synthesis = {
  collection_id: "c1",
  content: "## 全体像\nプロセスとシステムコール",
  connections: [
    {
      id: "c1",
      title: "コンテキストスイッチ",
      note_ids: ["n1", "n2"],
      explanation: "参考の説明",
      question: "どう関係しますか？",
    },
  ],
  contradictions: [{ note_ids: ["n1"], description: "食い違い" }],
  gaps: ["割り込み"],
  generated_at: "2026-10-03T00:00:00Z",
  is_stale: false,
  changed_note_ids: [],
  insights: [
    {
      id: "i1",
      connection_title: "割り込みとの関係",
      content: "自分の説明",
      created_at: "",
    },
  ],
};

beforeEach(() => {
  fetchAPI.mockReset();
  toastError.mockReset();
});

describe("CollectionSynthesis", () => {
  it("shows the explanations added in the dialogue and links to it", () => {
    render(
      <CollectionSynthesis
        collectionId="c1"
        noteCount={2}
        initial={SYNTHESIS}
      />,
    );

    expect(screen.getByText("自分の説明")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "つながりを説明する" }),
    ).toHaveAttribute("href", "/collections/c1/synthesis");
  });

  it("asks for two notes before a synthesis can be made", () => {
    render(
      <CollectionSynthesis collectionId="c1" noteCount={1} initial={null} />,
    );

    expect(screen.getByRole("button", { name: "まとめを作る" })).toBeDisabled();
    expect(
      screen.getByText("まとめは2件以上のノートから作れます"),
    ).toBeInTheDocument();
  });

  it("generates and shows the draft", async () => {
    fetchAPI.mockResolvedValue(SYNTHESIS);
    render(
      <CollectionSynthesis collectionId="c1" noteCount={2} initial={null} />,
    );

    await userEvent.click(screen.getByRole("button", { name: "まとめを作る" }));

    await waitFor(() =>
      expect(fetchAPI).toHaveBeenCalledWith("/api/collections/c1/synthesis", {
        method: "POST",
      }),
    );
    expect(await screen.findByText("コンテキストスイッチ")).toBeInTheDocument();
    expect(screen.getByText("どう関係しますか？")).toBeInTheDocument();
    expect(screen.getByText("食い違い")).toBeInTheDocument();
    expect(screen.getByText("割り込み")).toBeInTheDocument();
  });

  it("tells the user when the source notes changed", () => {
    render(
      <CollectionSynthesis
        collectionId="c1"
        noteCount={2}
        initial={{ ...SYNTHESIS, is_stale: true }}
      />,
    );

    expect(
      screen.getByText(
        "元のノートが更新されています。作り直すと最新の内容で作り直します。",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "作り直す" }),
    ).toBeInTheDocument();
  });

  it("reports a failure", async () => {
    fetchAPI.mockRejectedValue(new Error("API error: 502"));
    render(
      <CollectionSynthesis collectionId="c1" noteCount={2} initial={null} />,
    );

    await userEvent.click(screen.getByRole("button", { name: "まとめを作る" }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("まとめの作成に失敗しました"),
    );
  });
});
