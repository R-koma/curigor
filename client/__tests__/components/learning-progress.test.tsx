import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
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
});
