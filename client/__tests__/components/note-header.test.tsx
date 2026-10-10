import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NoteDates, NoteHeader } from "@/components/notes/note-header";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn(), replace: vi.fn() }),
}));

const PROPS = {
  id: "n1",
  topic: "二分探索",
  status: "completed",
  category: null,
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-03T00:00:00Z",
  reviewCount: 2,
  summary: "要約",
  content: "本文",
};

describe("NoteHeader", () => {
  it("offers a single back link on phones and the breadcrumb from md up", () => {
    render(<NoteHeader {...PROPS} />);
    const back = screen.getByRole("link", { name: "ノート一覧に戻る" });
    expect(back).toHaveAttribute("href", "/notes");
    expect(back).toHaveClass("md:hidden");
    const breadcrumb = screen.getByLabelText("パンくずリスト");
    expect(breadcrumb).toHaveClass("hidden", "md:flex");
  });

  it("keeps review out of the header on phones", () => {
    render(<NoteHeader {...PROPS} />);
    expect(screen.getByRole("link", { name: "復習する" })).toHaveClass(
      "max-md:hidden",
    );
  });

  it("keeps edit and copy next to the title", () => {
    render(<NoteHeader {...PROPS} />);
    expect(screen.getByRole("link", { name: "ノートを編集" })).toHaveAttribute(
      "href",
      "/notes/n1?edit=1",
    );
    expect(
      screen.getByRole("button", { name: "ノートをコピー" }),
    ).toBeInTheDocument();
  });

  it("hides the dates from the header on phones", () => {
    render(<NoteHeader {...PROPS} />);
    expect(screen.getByText("作成 2026年6月1日")).toHaveClass("max-md:hidden");
    expect(screen.getByText("復習 2 回")).not.toHaveClass("max-md:hidden");
  });
});

describe("NoteDates", () => {
  it("shows the update date only when it differs", () => {
    const { rerender } = render(
      <NoteDates createdAt={PROPS.createdAt} updatedAt={PROPS.updatedAt} />,
    );
    expect(screen.getByText("更新 2026年6月3日")).toBeInTheDocument();
    rerender(
      <NoteDates createdAt={PROPS.createdAt} updatedAt={PROPS.createdAt} />,
    );
    expect(screen.queryByText(/更新/)).not.toBeInTheDocument();
  });
});
