import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StudyMemoEditForm } from "@/components/study-memos/study-memo-edit-form";
import type { StudyMemo } from "@/lib/study-memos";

const mocks = vi.hoisted(() => ({
  fetchAPI: vi.fn(),
  push: vi.fn(),
  refresh: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ fetchAPI: mocks.fetchAPI }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: mocks.push,
    refresh: mocks.refresh,
  }),
}));
vi.mock("sonner", () => ({ toast: { error: mocks.toastError } }));

const MEMO: StudyMemo = {
  id: "m1",
  topic: "MECE",
  source: "",
  summary: "",
  overview: [],
  glossary: [
    { term: "MECE", reading: "ミーシー", meaning: "漏れなく重なりなく" },
    { term: "法人", reading: "", meaning: "会社や団体" },
  ],
  questions: [
    { question: "MECEとは", answer: "漏れなく重なりなく分ける考え方" },
    { question: "例は", answer: "顧客を個人と法人に分ける" },
  ],
  created_at: "2026-10-17T00:00:00Z",
};

function sentBody() {
  const [, init] = mocks.fetchAPI.mock.calls[0];
  return JSON.parse(init.body);
}

beforeEach(() => {
  mocks.fetchAPI.mockReset();
  mocks.push.mockReset();
  mocks.refresh.mockReset();
  mocks.toastError.mockReset();
});

describe("StudyMemoEditForm", () => {
  it("sends the edited summary and the remaining items with their original indices", async () => {
    mocks.fetchAPI.mockResolvedValue(MEMO);
    const user = userEvent.setup();
    render(<StudyMemoEditForm memo={MEMO} />);

    await user.type(screen.getByLabelText("要約"), "分け方の考え方");
    await user.click(screen.getByRole("button", { name: "用語 2 を削除" }));
    await user.click(screen.getByRole("button", { name: "疑問 1 を削除" }));
    await user.clear(screen.getByLabelText("疑問 1 の回答"));
    await user.type(screen.getByLabelText("疑問 1 の回答"), "顧客の分類");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() =>
      expect(mocks.push).toHaveBeenCalledWith("/study-memos/m1"),
    );
    expect(mocks.fetchAPI.mock.calls[0][0]).toBe("/api/study-memos/m1");
    expect(sentBody()).toEqual({
      topic: "MECE",
      summary: "分け方の考え方",
      questions: [{ index: 1, question: "例は", answer: "顧客の分類" }],
      glossary: [
        {
          index: 0,
          term: "MECE",
          reading: "ミーシー",
          meaning: "漏れなく重なりなく",
        },
      ],
    });
    expect(mocks.refresh).toHaveBeenCalled();
  });

  it("does not save without a topic", async () => {
    const user = userEvent.setup();
    render(<StudyMemoEditForm memo={MEMO} />);

    await user.clear(screen.getByLabelText("トピック"));
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(mocks.fetchAPI).not.toHaveBeenCalled();
    expect(mocks.toastError).toHaveBeenCalledWith("トピックは必須です");
  });

  it("goes back to the memo on cancel", async () => {
    const user = userEvent.setup();
    render(<StudyMemoEditForm memo={MEMO} />);

    await user.click(screen.getByRole("button", { name: "キャンセル" }));

    expect(mocks.push).toHaveBeenCalledWith("/study-memos/m1");
    expect(mocks.fetchAPI).not.toHaveBeenCalled();
  });

  it("keeps the form open when saving fails", async () => {
    mocks.fetchAPI.mockRejectedValue(new Error("failed"));
    const user = userEvent.setup();
    render(<StudyMemoEditForm memo={MEMO} />);

    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
    expect(mocks.push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "保存" })).toBeEnabled();
  });
});
