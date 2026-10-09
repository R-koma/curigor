import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { DrawerRecent } from "@/components/layout/drawer-recent";

const fetchAPI = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ fetchAPI }));

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

const SESSION = {
  session_id: "s1",
  session_type: "learning",
  status: "active",
  started_at: "2026-10-10T00:00:00Z",
  topic: "React の状態管理",
  note_id: null,
};

function notes(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: `n${i + 1}`,
    topic: `ノート${i + 1}`,
  }));
}

function respond(active: unknown, noteList: unknown) {
  fetchAPI.mockImplementation((path: string) => {
    if (path === "/api/dialogue-sessions/active") {
      return active instanceof Error
        ? Promise.reject(active)
        : Promise.resolve(active);
    }
    if (path === "/api/notes") {
      return noteList instanceof Error
        ? Promise.reject(noteList)
        : Promise.resolve({ notes: noteList });
    }
    return Promise.reject(new Error(path));
  });
}

describe("DrawerRecent", () => {
  beforeEach(() => {
    fetchAPI.mockReset();
  });

  it("links the resumable session", async () => {
    respond(SESSION, []);
    render(<DrawerRecent />);
    expect(
      await screen.findByRole("link", { name: /React の状態管理/ }),
    ).toHaveAttribute("href", "/learn?session=s1");
  });

  it("lists at most five recent notes in the order received and links to all notes", async () => {
    respond(null, notes(7));
    render(<DrawerRecent />);
    await screen.findByRole("link", { name: "ノート1" });
    const links = screen
      .getAllByRole("link")
      .filter((a) => a.getAttribute("href")?.startsWith("/notes/"));
    expect(links.map((a) => a.textContent)).toEqual([
      "ノート1",
      "ノート2",
      "ノート3",
      "ノート4",
      "ノート5",
    ]);
    expect(screen.getByRole("link", { name: /すべて見る/ })).toHaveAttribute(
      "href",
      "/notes",
    );
    expect(screen.queryByText("続きから")).toBeNull();
  });

  it("skips a review session that has no note to resume on", async () => {
    respond({ ...SESSION, session_type: "review", note_id: null }, []);
    render(<DrawerRecent />);
    expect(
      await screen.findByText("まだノートはありません"),
    ).toBeInTheDocument();
    expect(screen.queryByText("続きから")).toBeNull();
  });

  it("hides only the section whose request failed", async () => {
    respond(SESSION, new Error("500"));
    render(<DrawerRecent />);
    expect(
      await screen.findByRole("link", { name: /React の状態管理/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText("最近のノート")).toBeNull();
  });
});
