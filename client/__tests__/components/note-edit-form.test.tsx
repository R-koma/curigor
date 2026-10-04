import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NoteEditForm } from "@/components/notes/note-edit-form";

const push = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
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
  push.mockReset();
  refresh.mockReset();
  fetchAPI.mockReset();
  toastError.mockReset();
});

function renderForm() {
  render(
    <NoteEditForm
      noteId="n1"
      initialTopic="Python"
      initialSummary="要約"
      initialContent="本文"
    />,
  );
}

describe("NoteEditForm", () => {
  it("renders the fields with initial values", () => {
    renderForm();
    expect(screen.getByLabelText("トピック")).toHaveValue("Python");
    expect(screen.getByLabelText("要約")).toHaveValue("要約");
    expect(screen.getByLabelText("内容（Markdown）")).toHaveValue("本文");
  });

  it("PATCHes the edited fields and returns to the note view on save", async () => {
    fetchAPI.mockResolvedValue(undefined);
    renderForm();

    await userEvent.clear(screen.getByLabelText("内容（Markdown）"));
    await userEvent.type(
      screen.getByLabelText("内容（Markdown）"),
      "新しい本文",
    );
    await userEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes/n1", {
        method: "PATCH",
        body: JSON.stringify({
          topic: "Python",
          summary: "要約",
          content: "新しい本文",
        }),
      });
    });
    expect(push).toHaveBeenCalledWith("/notes/n1");
    expect(refresh).toHaveBeenCalled();
  });

  it("blocks saving and shows an error when required fields are empty", async () => {
    renderForm();

    await userEvent.clear(screen.getByLabelText("内容（Markdown）"));
    await userEvent.click(screen.getByRole("button", { name: "保存" }));

    expect(toastError).toHaveBeenCalledWith("トピックと内容は必須です");
    expect(fetchAPI).not.toHaveBeenCalled();
  });

  it("shows an error and stays in edit mode when the API fails", async () => {
    fetchAPI.mockRejectedValue(new Error("boom"));
    renderForm();

    await userEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith(
        "ノートを保存できませんでした。もう一度お試しください",
      );
    });
    expect(push).not.toHaveBeenCalled();
  });

  it("returns to the note view without saving on cancel", async () => {
    renderForm();

    await userEvent.click(screen.getByRole("button", { name: "キャンセル" }));

    expect(push).toHaveBeenCalledWith("/notes/n1");
    expect(fetchAPI).not.toHaveBeenCalled();
  });
});
