import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SidebarCalendar } from "@/components/layout/sidebar-calendar";

const fetchAPI = vi.fn();
vi.mock("@/lib/api", () => ({
  fetchAPI: (...args: unknown[]) => fetchAPI(...args),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
  }: {
    href: string;
    children: React.ReactNode;
  }) => <a href={href}>{children}</a>,
}));

interface NotePayload {
  id: string;
  topic: string;
  created_at: string;
}
interface ReviewPayload {
  id: string;
  note_id: string;
  note_topic: string;
  next_review_at: string;
}

function mockData(notes: NotePayload[], reviews: ReviewPayload[]) {
  fetchAPI.mockImplementation((path: string) => {
    if (path === "/api/notes") return Promise.resolve({ notes });
    if (path === "/api/review-schedules/upcoming")
      return Promise.resolve({ review_schedules: reviews });
    return Promise.resolve({});
  });
}

// 実行日に依存しないよう、月送りで過去月／未来月へ移動してから日付を操作する
const now = new Date();
const prevMonthDay15 = new Date(now.getFullYear(), now.getMonth() - 1, 15, 12);
const nextMonthDay25 = new Date(now.getFullYear(), now.getMonth() + 1, 25, 12);

beforeEach(() => {
  fetchAPI.mockReset();
});

describe("SidebarCalendar", () => {
  it("shows learned notes for a past day, linking to the note", async () => {
    mockData(
      [
        {
          id: "n1",
          topic: "React の状態管理",
          created_at: prevMonthDay15.toISOString(),
        },
      ],
      [],
    );
    const user = userEvent.setup();
    render(<SidebarCalendar />);

    await user.click(await screen.findByLabelText("前月"));
    await user.click(await screen.findByText("15"));

    const link = await screen.findByRole("link", { name: /React の状態管理/ });
    expect(link).toHaveAttribute("href", "/notes/n1");
  });

  it("shows upcoming reviews for a future day, linking to the note", async () => {
    mockData(
      [],
      [
        {
          id: "r1",
          note_id: "n9",
          note_topic: "二分探索",
          next_review_at: nextMonthDay25.toISOString(),
        },
      ],
    );
    const user = userEvent.setup();
    render(<SidebarCalendar />);

    await user.click(await screen.findByLabelText("翌月"));
    await user.click(await screen.findByText("25"));

    // 復習予定（border ドット）として note_id へリンクする
    const link = await screen.findByRole("link", { name: /二分探索/ });
    expect(link).toHaveAttribute("href", "/notes/n9");
  });

  it("does nothing when clicking a future day without a scheduled review", async () => {
    mockData([], []);
    const user = userEvent.setup();
    render(<SidebarCalendar />);

    await user.click(await screen.findByLabelText("翌月"));
    await user.click(screen.getByText("15"));

    // 選択されずパネルが出ない（無反応）
    expect(
      screen.queryByText("この日の学習記録はありません"),
    ).not.toBeInTheDocument();
  });

  it("shows an empty state for a past day without records", async () => {
    mockData([], []);
    const user = userEvent.setup();
    render(<SidebarCalendar />);

    await user.click(await screen.findByLabelText("前月"));
    await user.click(await screen.findByText("15"));

    expect(
      await screen.findByText("この日の学習記録はありません"),
    ).toBeInTheDocument();
  });

  it("returns to the current month via the 今日 button", async () => {
    mockData([], []);
    const user = userEvent.setup();
    render(<SidebarCalendar />);

    await user.click(await screen.findByLabelText("翌月"));
    await user.click(await screen.findByRole("button", { name: "今日" }));

    // 年表示は1月・12月のみ。それ以外は月だけ
    const showYear = now.getMonth() === 0 || now.getMonth() === 11;
    const currentLabel = showYear
      ? `${now.getFullYear()}年 ${now.getMonth() + 1}月`
      : `${now.getMonth() + 1}月`;
    expect(screen.getByText(currentLabel)).toBeInTheDocument();
  });

  it("shows a loading skeleton by default while data is in flight", () => {
    fetchAPI.mockImplementation(() => new Promise(() => {})); // 解決しない=読み込み中を維持
    render(<SidebarCalendar />);

    expect(document.querySelector('[data-slot="skeleton"]')).not.toBeNull();
  });

  it("renders nothing while loading when showSkeleton is false", () => {
    fetchAPI.mockImplementation(() => new Promise(() => {}));
    const { container } = render(<SidebarCalendar showSkeleton={false} />);

    expect(document.querySelector('[data-slot="skeleton"]')).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });

  it("fetches both notes and upcoming reviews", async () => {
    mockData([], []);
    render(<SidebarCalendar />);

    await waitFor(() => {
      expect(fetchAPI).toHaveBeenCalledWith("/api/notes");
      expect(fetchAPI).toHaveBeenCalledWith("/api/review-schedules/upcoming");
    });
  });
});
