import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
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
});
