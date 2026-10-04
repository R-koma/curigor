import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NoteCategoryEditor } from "@/components/notes/note-category-editor";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

const fetchAPI = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchAPI: (...args: unknown[]) => fetchAPI(...args),
}));

const toastError = vi.fn();
vi.mock("sonner", () => ({
  toast: { error: (msg: string) => toastError(msg) },
}));

beforeEach(() => {
  refresh.mockReset();
  fetchAPI.mockReset();
  toastError.mockReset();
});

describe("NoteCategoryEditor", () => {
  it("shows the add prompt when no category is set", () => {
    render(<NoteCategoryEditor noteId="n1" category={null} />);
    expect(screen.getByText("カテゴリーを追加")).toBeInTheDocument();
  });

  it("shows the category when set", () => {
    render(<NoteCategoryEditor noteId="n1" category="数学" />);
    expect(screen.getByText("数学")).toBeInTheDocument();
  });

  it("PATCHes the new category and refreshes on save", async () => {
    fetchAPI.mockResolvedValue(undefined);
    render(<NoteCategoryEditor noteId="n1" category={null} />);

    await userEvent.click(screen.getByLabelText("カテゴリーを編集"));
    await userEvent.type(
      screen.getByLabelText("カテゴリー名"),
      "プログラミング",
    );
    await userEvent.click(screen.getByLabelText("保存"));

    await waitFor(() => {
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes/n1", {
        method: "PATCH",
        body: JSON.stringify({ category: "プログラミング" }),
      });
    });
    expect(refresh).toHaveBeenCalled();
  });

  it("does not call the API when the value is unchanged", async () => {
    render(<NoteCategoryEditor noteId="n1" category="数学" />);

    await userEvent.click(screen.getByLabelText("カテゴリーを編集"));
    await userEvent.click(screen.getByLabelText("保存"));

    expect(fetchAPI).not.toHaveBeenCalled();
  });

  it("shows an error toast when the API fails", async () => {
    fetchAPI.mockRejectedValue(new Error("boom"));
    render(<NoteCategoryEditor noteId="n1" category={null} />);

    await userEvent.click(screen.getByLabelText("カテゴリーを編集"));
    await userEvent.type(screen.getByLabelText("カテゴリー名"), "数学");
    await userEvent.click(screen.getByLabelText("保存"));

    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith(
        "カテゴリーを更新できませんでした。もう一度お試しください",
      );
    });
    expect(refresh).not.toHaveBeenCalled();
  });
});
