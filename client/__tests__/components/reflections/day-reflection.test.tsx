import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DayReflectionView } from "@/components/reflections/day-reflection";
import type { DayReflection, ReflectionTopic } from "@/lib/reflection";

function topic(overrides: Partial<ReflectionTopic> = {}): ReflectionTopic {
  return {
    session_type: "learning",
    source_id: "11111111-1111-1111-1111-111111111111",
    topic: "TCP の 3 ウェイハンドシェイク",
    summary: "3 往復で接続を確立する。",
    struggles: ["なぜ 2 往復では足りないのか"],
    questions: [],
    ...overrides,
  };
}

describe("DayReflectionView", () => {
  it("shows a heading per session type when there are two or more", () => {
    const reflection: DayReflection = {
      day: "2026-11-01",
      groups: [
        { session_type: "learning", topics: [topic()] },
        {
          session_type: "explore",
          topics: [
            topic({
              session_type: "explore",
              source_id: "22222222-2222-2222-2222-222222222222",
              topic: "光合成の明反応",
              summary: "光で水を分解して ATP を作る。",
              struggles: [],
              questions: [
                { question: "暗反応は？", answer: "明るくても起きる" },
              ],
            }),
          ],
        },
      ],
    };
    render(<DayReflectionView reflection={reflection} isToday />);
    expect(screen.getByText("説明して学ぶ")).toBeInTheDocument();
    expect(screen.getByText("インプット")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "TCP の 3 ウェイハンドシェイク" }),
    ).toBeInTheDocument();
    expect(screen.getByText("3 往復で接続を確立する。")).toBeInTheDocument();
  });

  it("omits the session type heading when there is only one", () => {
    render(
      <DayReflectionView
        reflection={{
          day: "2026-11-01",
          groups: [{ session_type: "learning", topics: [topic()] }],
        }}
        isToday
      />,
    );
    expect(screen.queryByText("説明して学ぶ")).not.toBeInTheDocument();
  });

  it("titles today and other days differently", () => {
    const reflection: DayReflection = {
      day: "2026-11-01",
      groups: [{ session_type: "learning", topics: [topic()] }],
    };
    const { rerender } = render(
      <DayReflectionView reflection={reflection} isToday />,
    );
    expect(
      screen.getByRole("heading", { level: 2, name: "今日学んだこと" }),
    ).toBeInTheDocument();
    rerender(<DayReflectionView reflection={reflection} isToday={false} />);
    expect(
      screen.getByRole("heading", { level: 2, name: "11月1日に学んだこと" }),
    ).toBeInTheDocument();
    expect(screen.getByText("11月1日（日）")).toBeInTheDocument();
  });

  it("shows the empty state without buttons when nothing was learned", () => {
    render(
      <DayReflectionView
        reflection={{ day: "2026-11-01", groups: [] }}
        isToday
      />,
    );
    expect(screen.getByText("この日の学習はありません")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
