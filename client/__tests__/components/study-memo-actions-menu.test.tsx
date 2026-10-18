import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StudyMemoActionsMenu } from "@/components/study-memos/study-memo-actions-menu";

const mocks = vi.hoisted(() => ({
  fetchAPI: vi.fn(),
  replace: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ fetchAPI: mocks.fetchAPI }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mocks.replace,
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));
vi.mock("sonner", () => ({
  toast: { success: mocks.toastSuccess, error: mocks.toastError },
}));

async function confirmDelete() {
  render(<StudyMemoActionsMenu memoId="m1" topic="MECE" />);
  await userEvent.click(screen.getByRole("button", { name: "その他の操作" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "削除" }));
  return screen.findByRole("alertdialog", { name: "学習メモを削除しますか？" });
}

beforeEach(() => {
  mocks.fetchAPI.mockReset();
  mocks.replace.mockReset();
  mocks.toastSuccess.mockReset();
  mocks.toastError.mockReset();
});

describe("StudyMemoActionsMenu", () => {
  it("links 編集 to the edit view of the memo", async () => {
    render(<StudyMemoActionsMenu memoId="m1" topic="MECE" />);
    await userEvent.click(screen.getByRole("button", { name: "その他の操作" }));

    expect(
      await screen.findByRole("menuitem", { name: "編集" }),
    ).toHaveAttribute("href", "/study-memos/m1?edit=1");
  });

  it("deletes the memo after confirming and goes back to the list", async () => {
    mocks.fetchAPI.mockResolvedValue(undefined);
    const dialog = await confirmDelete();
    expect(dialog).toHaveTextContent("「MECE」を削除します");

    await userEvent.click(screen.getByRole("button", { name: "削除" }));

    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/study-memos"),
    );
    expect(mocks.fetchAPI).toHaveBeenCalledWith("/api/study-memos/m1", {
      method: "DELETE",
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("学習メモを削除しました");
  });

  it("stays on the page and tells the user when deleting fails", async () => {
    mocks.fetchAPI.mockRejectedValue(new Error("failed"));
    await confirmDelete();

    await userEvent.click(screen.getByRole("button", { name: "削除" }));

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
    expect(mocks.replace).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "削除" })).toBeEnabled();
  });

  it("does not delete when cancelled", async () => {
    await confirmDelete();

    await userEvent.click(screen.getByRole("button", { name: "キャンセル" }));

    expect(mocks.fetchAPI).not.toHaveBeenCalled();
  });
});
