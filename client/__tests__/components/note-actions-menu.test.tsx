import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NoteActionsMenu } from "@/components/notes/note-actions-menu";

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

const PROPS = {
  noteId: "n1",
  topic: "React の状態管理",
  summary: "要約テキスト",
  content: "本文テキスト",
};

async function openMenu() {
  render(<NoteActionsMenu {...PROPS} />);
  await userEvent.click(screen.getByRole("button", { name: "その他の操作" }));
}

async function confirmDelete() {
  await openMenu();
  await userEvent.click(await screen.findByRole("menuitem", { name: "削除" }));
  const dialog = await screen.findByRole("alertdialog", {
    name: "ノートを削除しますか？",
  });
  return dialog;
}

beforeEach(() => {
  mocks.fetchAPI.mockReset();
  mocks.replace.mockReset();
  mocks.toastSuccess.mockReset();
  mocks.toastError.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("NoteActionsMenu", () => {
  it("shows the menu button without a border or fill, even while open", () => {
    render(<NoteActionsMenu {...PROPS} />);
    const trigger = screen.getByRole("button", { name: "その他の操作" });
    expect(trigger).toHaveAttribute("data-variant", "ghost");
    expect(trigger).toHaveClass(
      "hover:bg-transparent",
      "aria-expanded:bg-transparent",
    );
  });

  it("does not move focus back to the button after choosing with the pointer", async () => {
    vi.stubGlobal("navigator", {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    await openMenu();
    await userEvent.click(
      await screen.findByRole("menuitem", { name: "Markdown をコピー" }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("menu")).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "その他の操作" }),
    ).not.toHaveFocus();
  });

  it("does not move focus back to the button after tapping outside", async () => {
    await openMenu();
    await screen.findByRole("menu");
    await userEvent.setup({ pointerEventsCheck: 0 }).click(document.body);
    await waitFor(() =>
      expect(screen.queryByRole("menu")).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "その他の操作" }),
    ).not.toHaveFocus();
  });

  it("moves focus back to the button after closing with the keyboard", async () => {
    render(<NoteActionsMenu {...PROPS} />);
    const trigger = screen.getByRole("button", { name: "その他の操作" });
    trigger.focus();
    await userEvent.keyboard("{Enter}");
    await screen.findByRole("menu");
    await userEvent.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("menu")).not.toBeInTheDocument(),
    );
    expect(trigger).toHaveFocus();
  });

  it("lists edit, copy and delete with labels", async () => {
    await openMenu();
    expect(
      await screen.findByRole("menuitem", { name: "編集" }),
    ).toHaveAttribute("href", "/notes/n1?edit=1");
    expect(
      screen.getByRole("menuitem", { name: "Markdown をコピー" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "削除" })).toBeInTheDocument();
  });

  it("copies the note as markdown", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    await openMenu();
    await userEvent.click(
      await screen.findByRole("menuitem", { name: "Markdown をコピー" }),
    );
    await waitFor(() => expect(mocks.toastSuccess).toHaveBeenCalledOnce());
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toContain("# React の状態管理");
    expect(copied).toContain("本文テキスト");
  });

  it("tells when the clipboard is unavailable", async () => {
    vi.stubGlobal("navigator", {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });
    await openMenu();
    await userEvent.click(
      await screen.findByRole("menuitem", { name: "Markdown をコピー" }),
    );
    await waitFor(() => expect(mocks.toastError).toHaveBeenCalledOnce());
    expect(mocks.toastSuccess).not.toHaveBeenCalled();
  });

  it("asks before deleting and says what else goes away", async () => {
    const dialog = await confirmDelete();
    expect(dialog).toHaveTextContent("「React の状態管理」");
    expect(dialog).toHaveTextContent("フィードバックと復習の予定も削除");
    expect(mocks.fetchAPI).not.toHaveBeenCalled();
  });

  it("keeps the note when the deletion is cancelled", async () => {
    await confirmDelete();
    await userEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(mocks.fetchAPI).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("deletes the note and goes back to the list", async () => {
    mocks.fetchAPI.mockResolvedValue(undefined);
    await confirmDelete();
    await userEvent.click(screen.getByRole("button", { name: "削除" }));
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/notes"));
    expect(mocks.fetchAPI).toHaveBeenCalledWith("/api/notes/n1", {
      method: "DELETE",
    });
    expect(mocks.toastSuccess).toHaveBeenCalledOnce();
  });

  it("stays on the note and tells when the deletion fails", async () => {
    mocks.fetchAPI.mockRejectedValue(new Error("500"));
    await confirmDelete();
    await userEvent.click(screen.getByRole("button", { name: "削除" }));
    await waitFor(() => expect(mocks.toastError).toHaveBeenCalledOnce());
    expect(mocks.replace).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "削除" })).toBeEnabled();
  });

  it("does not delete twice while a deletion is in flight", async () => {
    mocks.fetchAPI.mockReturnValue(new Promise(() => {}));
    await confirmDelete();
    await userEvent.click(screen.getByRole("button", { name: "削除" }));
    const pending = screen.getByRole("button", { name: /削除中/ });
    expect(pending).toBeDisabled();
    await userEvent.click(pending);
    expect(mocks.fetchAPI).toHaveBeenCalledOnce();
  });
});
