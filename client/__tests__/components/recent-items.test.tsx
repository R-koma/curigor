import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { RecentItems } from "@/components/layout/recent-items";

const fetchAPI = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ fetchAPI }));

const pathname = vi.hoisted(() => ({ current: "/dashboard" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.current }));

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
  topic: "React の状態管理",
  note_id: null,
  last_activity_at: "2026-10-10T00:00:00Z",
  expires_at: "2026-11-10T00:00:00Z",
  last_assistant_excerpt: null,
  progress: null,
};

function sessions(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    ...SESSION,
    session_id: `s${i + 1}`,
    topic: `会話${i + 1}`,
  }));
}

function notes(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: `n${i + 1}`,
    topic: `ノート${i + 1}`,
  }));
}

function respond(active: unknown, noteList: unknown) {
  fetchAPI.mockImplementation((path: string) => {
    if (path === "/api/dialogue-sessions/saved") {
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

describe("RecentItems", () => {
  beforeEach(() => {
    fetchAPI.mockReset();
    pathname.current = "/dashboard";
  });

  it("refetches the sessions when the path changes", async () => {
    respond([], []);
    const view = render(<RecentItems />);
    await screen.findByText("まだノートはありません");
    expect(screen.queryByText("続きから")).toBeNull();

    respond([SESSION], []);
    pathname.current = "/learn";
    await act(async () => {
      view.rerender(<RecentItems />);
    });
    expect(
      await screen.findByRole("link", { name: /React の状態管理/ }),
    ).toBeInTheDocument();

    respond([], []);
    pathname.current = "/dashboard";
    await act(async () => {
      view.rerender(<RecentItems />);
    });
    await screen.findByText("まだノートはありません");
    expect(screen.queryByText("続きから")).toBeNull();
  });

  it("counts and slices only the sessions that can be linked", async () => {
    const noNote = { ...SESSION, session_type: "review", note_id: null };
    respond([noNote, noNote, noNote, ...sessions(4)], []);
    render(<RecentItems />);
    await screen.findByRole("link", { name: /会話1/ });
    expect(screen.getByRole("link", { name: /会話3/ })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "すべて見る（4）" }),
    ).toBeInTheDocument();
  });

  it("links the resumable session", async () => {
    respond([SESSION], []);
    render(<RecentItems />);
    expect(
      await screen.findByRole("link", { name: /React の状態管理/ }),
    ).toHaveAttribute("href", "/learn?session=s1");
  });

  it.each([
    ["learning", "説明する"],
    ["explore", "理解する"],
    ["review", "復習"],
  ] as const)("labels a resumable %s session as %s", async (type, label) => {
    respond([{ ...SESSION, session_type: type, note_id: "n1" }], []);
    render(<RecentItems />);
    expect(
      await screen.findByRole("link", { name: /React の状態管理/ }),
    ).toHaveTextContent(label);
  });

  it("lists at most five recent notes in the order received and links to all notes", async () => {
    respond([], notes(7));
    render(<RecentItems />);
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
    expect(screen.getByRole("link", { name: "すべて見る" })).toHaveAttribute(
      "href",
      "/notes",
    );
    expect(screen.queryByText("続きから")).toBeNull();
  });

  it("shows the three most recent sessions in the order received and a link to all", async () => {
    respond(sessions(5), []);
    render(<RecentItems />);
    await screen.findByRole("link", { name: /会話1/ });
    const links = screen
      .getAllByRole("link")
      .filter((a) => a.getAttribute("href")?.startsWith("/learn"));
    expect(links.map((a) => a.textContent)).toEqual([
      expect.stringContaining("会話1"),
      expect.stringContaining("会話2"),
      expect.stringContaining("会話3"),
    ]);
    expect(
      screen.getByRole("link", { name: "すべて見る（5）" }),
    ).toHaveAttribute("href", "/sessions");
  });

  it("hides the section when nothing is saved", async () => {
    respond([], []);
    render(<RecentItems />);
    await screen.findByText("まだノートはありません");
    expect(screen.queryByText("続きから")).toBeNull();
    expect(screen.queryByRole("link", { name: /すべて見る（/ })).toBeNull();
  });

  it("skips a review session that has no note to resume on", async () => {
    respond([{ ...SESSION, session_type: "review", note_id: null }], []);
    render(<RecentItems />);
    expect(
      await screen.findByText("まだノートはありません"),
    ).toBeInTheDocument();
    expect(screen.queryByText("続きから")).toBeNull();
  });

  it("hides only the section whose request failed", async () => {
    respond([SESSION], new Error("500"));
    render(<RecentItems />);
    expect(
      await screen.findByRole("link", { name: /React の状態管理/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText("最近のノート")).toBeNull();
  });
});
