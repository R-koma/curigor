import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LearningProgressIndicator } from "@/components/chat/learning-progress";

describe("LearningProgressIndicator", () => {
  it("shows reached count over target and lists reached aspects", () => {
    render(
      <LearningProgressIndicator
        progress={{
          reached_aspects: ["計算量", "前提条件"],
          target_count: 3,
          is_complete: false,
        }}
      />,
    );

    expect(screen.getByText("2/3")).toBeInTheDocument();
    expect(
      screen.getByTitle("説明できた観点: 計算量、前提条件"),
    ).toBeInTheDocument();
  });

  it("caps the count at the target when more aspects are reached", () => {
    render(
      <LearningProgressIndicator
        progress={{
          reached_aspects: ["A", "B", "C", "D"],
          target_count: 3,
          is_complete: true,
        }}
      />,
    );

    expect(screen.getByText("3/3")).toBeInTheDocument();
  });

  it("explains the empty state", () => {
    render(
      <LearningProgressIndicator
        progress={{ reached_aspects: [], target_count: 3, is_complete: false }}
      />,
    );

    expect(screen.getByText("0/3")).toBeInTheDocument();
    expect(
      screen.getByTitle("まだ説明できた観点はありません"),
    ).toBeInTheDocument();
  });

  it("opens the depth map panel when aspects are present", async () => {
    render(
      <LearningProgressIndicator
        progress={{
          reached_aspects: [],
          target_count: 1,
          is_complete: false,
          aspects: [
            { name: "値の埋め込み方", is_core: true, reached_stage: "defined" },
          ],
        }}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "観点ごとの到達度を表示" }),
    );

    expect(
      await screen.findByText(
        "次は、なぜ必要か・どう成り立つかを説明してみましょう",
      ),
    ).toBeInTheDocument();
  });

  it("stays a plain indicator without aspects", () => {
    render(
      <LearningProgressIndicator
        progress={{
          reached_aspects: [],
          target_count: 3,
          is_complete: false,
          aspects: [],
        }}
      />,
    );

    expect(screen.queryByRole("button")).toBeNull();
  });
});
