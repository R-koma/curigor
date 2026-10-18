import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { COARSE_POINTER, setMediaQuery } from "../stubs/match-media";
import { StudyMemoList } from "@/components/study-memos/study-memo-list";
import type { StudyMemoSummary } from "@/lib/study-memos";

const mocks = vi.hoisted(() => ({
  fetchAPI: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ fetchAPI: mocks.fetchAPI }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mocks.replace,
    push: vi.fn(),
    refresh: mocks.refresh,
  }),
}));
vi.mock("sonner", () => ({
  toast: { success: mocks.toastSuccess, error: mocks.toastError },
}));

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
    origin_note_id: null,
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

  it("sends a memo made from a note's improvement to reviewing that note", () => {
    render(
      <StudyMemoList
        memos={[{ ...memo("m1", "二分探索"), origin_note_id: "n7" }]}
      />,
    );

    expect(
      screen.getByRole("link", { name: "元のノートを復習する" }),
    ).toHaveAttribute("href", "/review/n7");
    expect(
      screen.queryByRole("link", { name: "説明してみる" }),
    ).not.toBeInTheDocument();
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

describe("StudyMemoList deletion", () => {
  beforeEach(() => {
    Object.values(mocks).forEach((mock) => mock.mockReset());
  });

  async function openDeleteDialog() {
    await userEvent.click(screen.getByRole("button", { name: "その他の操作" }));
    await userEvent.click(
      await screen.findByRole("menuitem", { name: "削除" }),
    );
    return screen.findByRole("alertdialog", {
      name: "学習メモを削除しますか？",
    });
  }

  it("links 編集 in the more-actions menu to the edit view of the memo", async () => {
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);
    await userEvent.click(screen.getByRole("button", { name: "その他の操作" }));

    expect(
      await screen.findByRole("menuitem", { name: "編集" }),
    ).toHaveAttribute("href", "/study-memos/m1?edit=1");
  });

  it("deletes the memo after confirming and stays on the list", async () => {
    mocks.fetchAPI.mockResolvedValue(undefined);
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);
    const dialog = await openDeleteDialog();
    expect(dialog).toHaveTextContent("「二分探索」を削除します");

    await userEvent.click(screen.getByRole("button", { name: "削除" }));

    await waitFor(() => expect(mocks.refresh).toHaveBeenCalled());
    expect(mocks.fetchAPI).toHaveBeenCalledWith("/api/study-memos/m1", {
      method: "DELETE",
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("学習メモを削除しました");
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("keeps the dialog open and tells the user when deleting fails", async () => {
    mocks.fetchAPI.mockRejectedValue(new Error("failed"));
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);
    await openDeleteDialog();

    await userEvent.click(screen.getByRole("button", { name: "削除" }));

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
    expect(mocks.refresh).not.toHaveBeenCalled();
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("hides the more-actions menu on a coarse pointer and deletes by swiping", async () => {
    act(() => setMediaQuery(COARSE_POINTER, true));
    render(<StudyMemoList memos={[memo("m1", "二分探索")]} />);
    expect(
      screen.getByRole("button", { name: "その他の操作" }).className,
    ).toContain("pointer-coarse:hidden");

    const card = screen.getByText("二分探索");
    fireEvent.touchStart(card, { touches: [{ clientX: 200, clientY: 0 }] });
    fireEvent.touchMove(card, { touches: [{ clientX: 150, clientY: 0 }] });
    fireEvent.touchMove(card, { touches: [{ clientX: 80, clientY: 0 }] });
    fireEvent.touchEnd(card, { changedTouches: [{ clientX: 80 }] });
    fireEvent.click(screen.getByRole("button", { name: "「二分探索」を削除" }));

    expect(
      await screen.findByRole("alertdialog", {
        name: "学習メモを削除しますか？",
      }),
    ).toBeInTheDocument();
  });
});
