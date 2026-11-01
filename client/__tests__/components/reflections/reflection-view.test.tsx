import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReflectionView } from "@/components/reflections/reflection-view";
import type { DayReflection, WeekDayStatus } from "@/lib/reflection";

const mocks = vi.hoisted(() => ({
  fetchAPI: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ fetchAPI: mocks.fetchAPI }));
vi.mock("sonner", () => ({ toast: { error: mocks.toastError } }));

const DAYS: WeekDayStatus[] = [
  { day: "2026-10-26", has_learning: false, unread: false },
  { day: "2026-10-27", has_learning: true, unread: true },
  { day: "2026-10-28", has_learning: false, unread: false },
  { day: "2026-10-29", has_learning: false, unread: false },
  { day: "2026-10-30", has_learning: false, unread: false },
  { day: "2026-10-31", has_learning: true, unread: true },
  { day: "2026-11-01", has_learning: false, unread: false },
];

function dayReflection(day: string, topic: string): DayReflection {
  return {
    day,
    groups: [
      {
        session_type: "learning",
        topics: [
          {
            session_type: "learning",
            source_id: `id-${day}`,
            topic,
            summary: `${topic}の要点`,
            struggles: [],
            questions: [],
          },
        ],
      },
    ],
  };
}

describe("ReflectionView", () => {
  beforeEach(() => {
    mocks.fetchAPI.mockReset();
    mocks.toastError.mockReset();
  });

  it("marks the initial day viewed and clears its dot", async () => {
    mocks.fetchAPI.mockResolvedValue(undefined);
    render(
      <ReflectionView
        initialDays={DAYS}
        initialReflection={dayReflection("2026-10-31", "DNS")}
        today="2026-11-01"
      />,
    );
    await waitFor(() =>
      expect(mocks.fetchAPI).toHaveBeenCalledWith(
        "/api/reflections/days/2026-10-31/view",
        { method: "PUT" },
      ),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /31/ }).getAttribute("aria-label"),
      ).not.toContain("未読"),
    );
    expect(
      screen.getByRole("heading", { name: "10月31日に学んだこと" }),
    ).toBeInTheDocument();
  });

  it("loads another day when it is selected", async () => {
    mocks.fetchAPI.mockImplementation(async (path: string) =>
      path === "/api/reflections/days/2026-10-27"
        ? dayReflection("2026-10-27", "TCP")
        : undefined,
    );
    render(
      <ReflectionView
        initialDays={DAYS}
        initialReflection={dayReflection("2026-10-31", "DNS")}
        today="2026-11-01"
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /27/ }));
    expect(
      await screen.findByRole("heading", { name: "TCP" }),
    ).toBeInTheDocument();
    expect(mocks.fetchAPI).toHaveBeenCalledWith(
      "/api/reflections/days/2026-10-27/view",
      { method: "PUT" },
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /27/ }).getAttribute("aria-label"),
      ).not.toContain("未読"),
    );
  });

  it("does not mark an empty day viewed", async () => {
    mocks.fetchAPI.mockResolvedValue(undefined);
    render(
      <ReflectionView
        initialDays={DAYS}
        initialReflection={{ day: "2026-11-01", groups: [] }}
        today="2026-11-01"
      />,
    );
    expect(screen.getByText("この日の学習はありません")).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 0));
    expect(mocks.fetchAPI).not.toHaveBeenCalled();
  });

  it("offers a retry when a day fails to load", async () => {
    mocks.fetchAPI.mockImplementation(async (path: string) => {
      if (path === "/api/reflections/days/2026-10-27") throw new Error("down");
      return undefined;
    });
    render(
      <ReflectionView
        initialDays={DAYS}
        initialReflection={dayReflection("2026-10-31", "DNS")}
        today="2026-11-01"
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /27/ }));
    expect(
      await screen.findByRole("button", { name: "もう一度読み込む" }),
    ).toBeInTheDocument();
  });

  it("moves to the previous week", async () => {
    const previous = DAYS.map((d, i) => ({
      day: `2026-10-${String(19 + i).padStart(2, "0")}`,
      has_learning: false,
      unread: false,
    }));
    mocks.fetchAPI.mockImplementation(async (path: string) =>
      path === "/api/reflections/weeks/2026-10-19/days"
        ? { days: previous }
        : undefined,
    );
    render(
      <ReflectionView
        initialDays={DAYS}
        initialReflection={dayReflection("2026-10-31", "DNS")}
        today="2026-11-01"
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "前の週" }));
    expect(await screen.findByText("10月19日の週")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "次の週" })).toBeEnabled();
  });
});
