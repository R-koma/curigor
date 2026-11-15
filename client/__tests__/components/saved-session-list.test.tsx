import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SavedSessionList } from "@/components/sessions/saved-session-list";
import type { SavedSession } from "@/lib/saved-sessions";

const fetchAPI = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ fetchAPI }));

interface ToastOptions {
  onAutoClose: () => void;
}
const toastMock = vi.hoisted(() => {
  const fn = vi.fn() as ReturnType<typeof vi.fn> & {
    error: ReturnType<typeof vi.fn>;
    dismiss: ReturnType<typeof vi.fn>;
  };
  fn.error = vi.fn();
  fn.dismiss = vi.fn();
  return fn;
});
vi.mock("sonner", () => ({ toast: toastMock }));

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

const NOW = new Date("2026-11-15T12:00:00Z");
const DAY = 86_400_000;

function session(overrides: Partial<SavedSession> = {}): SavedSession {
  return {
    session_id: "s1",
    session_type: "learning",
    topic: "TCP の輻輳制御",
    note_id: null,
    last_activity_at: new Date(NOW.getTime() - 3 * 3_600_000).toISOString(),
    expires_at: new Date(NOW.getTime() + 20 * DAY).toISOString(),
    last_assistant_excerpt: "スロースタートの後は？",
    progress: { reached: 2, target: 5 },
    ...overrides,
  };
}

describe("SavedSessionList", () => {
  beforeEach(() => {
    fetchAPI.mockReset();
    toastMock.mockReset();
    sessionStorage.clear();
  });

  it("shows the count in the description", () => {
    render(
      <SavedSessionList
        sessions={[session(), session({ session_id: "s2" })]}
        now={NOW}
      />,
    );
    expect(
      screen.getByText(/2 件 · 30 日触らないと自動で消えます/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/保存されるのは送った会話までです/),
    ).toBeInTheDocument();
  });

  it("renders topic, relative time, excerpt and kind with progress", () => {
    render(<SavedSessionList sessions={[session()]} now={NOW} />);
    expect(screen.getByText("TCP の輻輳制御")).toBeInTheDocument();
    expect(screen.getByText("3 時間前")).toBeInTheDocument();
    expect(screen.getByText("AI: スロースタートの後は？")).toBeInTheDocument();
    expect(screen.getByText("説明する · 観点 2/5")).toBeInTheDocument();
  });

  it("shows the kind alone without progress and a placeholder for no topic", () => {
    render(
      <SavedSessionList
        sessions={[
          session({ session_type: "explore", progress: null, topic: null }),
        ]}
        now={NOW}
      />,
    );
    expect(screen.getByText("理解する")).toBeInTheDocument();
    expect(screen.getByText("（タイトル未設定）")).toBeInTheDocument();
  });

  it("warns in red under seven days and not at eight", () => {
    const { rerender } = render(
      <SavedSessionList
        sessions={[
          session({
            expires_at: new Date(NOW.getTime() + 4 * DAY).toISOString(),
          }),
        ]}
        now={NOW}
      />,
    );
    expect(screen.getByText("あと 4 日で削除").className).toMatch(
      /text-destructive/,
    );
    rerender(
      <SavedSessionList
        sessions={[
          session({
            expires_at: new Date(NOW.getTime() + 8 * DAY).toISOString(),
          }),
        ]}
        now={NOW}
      />,
    );
    expect(screen.queryByText(/あと .* 日で削除/)).toBeNull();
    expect(screen.getByText("3 時間前")).toBeInTheDocument();
  });

  it("links each row to its resume target", () => {
    render(
      <SavedSessionList
        sessions={[
          session(),
          session({
            session_id: "r1",
            session_type: "review",
            note_id: "n9",
            topic: "復習のトピック",
          }),
        ]}
        now={NOW}
      />,
    );
    expect(
      screen.getByRole("link", { name: /TCP の輻輳制御/ }),
    ).toHaveAttribute("href", "/learn?session=s1");
    expect(
      screen.getByRole("link", { name: /復習のトピック/ }),
    ).toHaveAttribute("href", "/review/n9?session=r1");
  });

  it("deletes through the API and clears the draft once the toast closes", async () => {
    fetchAPI.mockResolvedValue(undefined);
    sessionStorage.setItem("curigor:draft:session:s1", "下書き");
    const user = userEvent.setup();
    render(<SavedSessionList sessions={[session()]} now={NOW} />);
    await user.click(
      screen.getByRole("button", { name: "「TCP の輻輳制御」を削除" }),
    );
    expect(screen.queryByText("TCP の輻輳制御")).toBeNull();
    expect(fetchAPI).not.toHaveBeenCalled();
    const options = toastMock.mock.calls[0][1] as ToastOptions;
    await vi.waitFor(async () => {
      options.onAutoClose();
      expect(fetchAPI).toHaveBeenCalledWith("/api/dialogue-sessions/s1", {
        method: "DELETE",
      });
    });
    await vi.waitFor(() =>
      expect(sessionStorage.getItem("curigor:draft:session:s1")).toBeNull(),
    );
  });

  it("shows the empty state with a link to start learning", () => {
    render(<SavedSessionList sessions={[]} now={NOW} />);
    expect(screen.getByText("保存中の会話はありません")).toBeInTheDocument();
    const empty = screen.getByText("保存中の会話はありません").parentElement!;
    expect(within(empty).getByRole("link")).toHaveAttribute("href", "/learn");
  });
});
