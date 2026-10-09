import { describe, it, expect, vi } from "vitest";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { COARSE_POINTER, setMediaQuery } from "../stubs/match-media";
import { NoteList } from "@/components/notes/note-list";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({ fetchAPI: vi.fn() }));

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

const NOTES = [
  {
    id: "n1",
    topic: "二分探索",
    content: "",
    summary: null,
    status: "active",
    category: "アルゴリズム",
    collection_id: null,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    review_count: 0,
  },
  {
    id: "n2",
    topic: "TCP の再送制御",
    content: "",
    summary: null,
    status: "archived",
    category: "ネットワーク",
    collection_id: null,
    created_at: "2026-10-02T00:00:00Z",
    updated_at: "2026-10-02T00:00:00Z",
    review_count: 1,
  },
];

describe("NoteList filters", () => {
  it("keeps the status switch and the category picker on one line", () => {
    render(<NoteList notes={NOTES} collections={[]} />);
    const row = screen.getByRole("group", { name: "絞り込み" });
    expect(row.className).toContain("flex-nowrap");
    expect(
      within(row).getByRole("button", { name: "すべて" }),
    ).toBeInTheDocument();
    const picker = within(row).getByRole("combobox");
    expect(picker.className).toContain("min-w-0");
    expect(picker.className).not.toMatch(/(^| )w-44( |$)/);
  });

  it("sizes the category picker to its label on every width", () => {
    render(<NoteList notes={NOTES} collections={[]} />);
    const picker = screen.getByRole("combobox");
    expect(picker.className).toContain("w-auto");
    expect(picker.className).not.toMatch(/w-44/);
    expect(picker.className).toContain("max-w-48");
  });
});

describe("NoteList deletion on touch", () => {
  it("hides the more-actions menu on a coarse pointer and deletes by swiping", async () => {
    act(() => setMediaQuery(COARSE_POINTER, true));
    render(<NoteList notes={NOTES} collections={[]} />);
    expect(
      screen.getAllByRole("button", { name: "その他の操作" })[0].className,
    ).toContain("pointer-coarse:hidden");
    const card = screen.getByText("二分探索");
    fireEvent.touchStart(card, { touches: [{ clientX: 200, clientY: 0 }] });
    fireEvent.touchMove(card, { touches: [{ clientX: 150, clientY: 0 }] });
    fireEvent.touchMove(card, { touches: [{ clientX: 80, clientY: 0 }] });
    fireEvent.touchEnd(card, { changedTouches: [{ clientX: 80 }] });
    fireEvent.click(screen.getByRole("button", { name: "「二分探索」を削除" }));
    expect(
      await screen.findByRole("alertdialog", {
        name: "ノートを削除しますか？",
      }),
    ).toBeInTheDocument();
  });
});
