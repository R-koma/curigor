import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WeekReflectionView } from "@/components/reflections/week-reflection";
import type { WeekReflection } from "@/lib/reflection";

const REFLECTION: WeekReflection = {
  week_start: "2026-10-26",
  days: [
    {
      day: "2026-10-27",
      topics: [{ session_type: "learning", source_id: "n1", topic: "TCP" }],
    },
    {
      day: "2026-10-31",
      topics: [
        { session_type: "explore", source_id: "m1", topic: "光合成" },
        { session_type: "review", source_id: "n2", topic: "DNS" },
      ],
    },
  ],
  struggles: [
    { topic: "TCP", kind: "struggle", text: "再送の条件", answer: null },
    {
      topic: "光合成",
      kind: "question",
      text: "暗反応は暗い所だけ？",
      answer: "明るくても起きる",
    },
  ],
};

describe("WeekReflectionView", () => {
  it("links each topic to its note or study memo", () => {
    render(<WeekReflectionView reflection={REFLECTION} isCurrentWeek />);
    expect(screen.getByRole("link", { name: "TCP" })).toHaveAttribute(
      "href",
      "/notes/n1",
    );
    expect(screen.getByRole("link", { name: "光合成" })).toHaveAttribute(
      "href",
      "/study-memos/m1",
    );
    expect(screen.getByRole("link", { name: "DNS" })).toHaveAttribute(
      "href",
      "/notes/n2",
    );
  });

  it("shows only the days with learning and their topics", () => {
    render(<WeekReflectionView reflection={REFLECTION} isCurrentWeek />);
    expect(
      screen.getByRole("heading", { name: "今週のまとめ" }),
    ).toBeInTheDocument();
    expect(screen.getByText("10月27日（火）")).toBeInTheDocument();
    expect(screen.getByText("10月31日（土）")).toBeInTheDocument();
    expect(screen.queryByText(/10月28日/)).not.toBeInTheDocument();
    expect(screen.getByText("TCP")).toBeInTheDocument();
    expect(screen.getByText("DNS")).toBeInTheDocument();
    expect(screen.queryByText("説明して学ぶ")).not.toBeInTheDocument();
  });

  it("keeps one closed accordion per kind with the topic before each item", async () => {
    render(<WeekReflectionView reflection={REFLECTION} isCurrentWeek />);
    const struggle = screen.getByRole("button", {
      name: "うまく説明できなかった所",
    });
    const question = screen.getByRole("button", { name: "出た疑問" });
    expect(struggle).toHaveAttribute("aria-expanded", "false");
    expect(question).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(struggle);
    const item = screen.getByText("再送の条件").closest("li");
    expect(item).not.toBeNull();
    expect(item?.textContent?.indexOf("TCP")).toBe(0);

    await userEvent.click(question);
    const qa = screen.getByText("暗反応は暗い所だけ？").closest("div");
    expect(within(qa as HTMLElement).getByText("光合成")).toBeVisible();
    expect(screen.getByText("明るくても起きる")).toBeVisible();
  });

  it("offers audio and the quiz for the week", () => {
    render(<WeekReflectionView reflection={REFLECTION} isCurrentWeek />);
    expect(
      screen.getByRole("button", { name: "音声で聞く" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "小テスト" }),
    ).toBeInTheDocument();
  });

  it("titles a past week by its Monday", () => {
    render(
      <WeekReflectionView reflection={REFLECTION} isCurrentWeek={false} />,
    );
    expect(
      screen.getByRole("heading", { name: "10月26日の週のまとめ" }),
    ).toBeInTheDocument();
  });

  it("shows the empty state without buttons when nothing was learned", () => {
    render(
      <WeekReflectionView
        reflection={{ week_start: "2026-10-26", days: [], struggles: [] }}
        isCurrentWeek
      />,
    );
    expect(screen.getByText("この週の学習はありません")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
