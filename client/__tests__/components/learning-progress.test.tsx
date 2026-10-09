import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  LearningProgressIndicator,
  ProgressAdvanceNotice,
} from "@/components/chat/learning-progress";

describe("LearningProgressIndicator", () => {
  it("shows reached count over target and lists reached aspects", async () => {
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
    await userEvent.tab();
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "説明できた観点: 計算量、前提条件",
    );
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

  it("explains the empty state", async () => {
    render(
      <LearningProgressIndicator
        progress={{ reached_aspects: [], target_count: 3, is_complete: false }}
      />,
    );

    expect(screen.getByText("0/3")).toBeInTheDocument();
    await userEvent.tab();
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "まだ説明できた観点はありません",
    );
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

    const trigger = screen.getByRole("button", {
      name: "観点ごとの到達度を表示",
    });
    expect(within(trigger).getByText("観点")).toBeInTheDocument();
    expect(within(trigger).getByText("0/1")).toBeInTheDocument();
    await userEvent.click(trigger);

    expect(
      await screen.findByText(
        "次は、なぜ必要か・どう成り立つかを説明してみましょう",
      ),
    ).toBeInTheDocument();
  });

  it("puts the learning premise above the depth map", async () => {
    render(
      <LearningProgressIndicator
        progress={{
          reached_aspects: [],
          target_count: 1,
          is_complete: false,
          aspects: [
            { name: "値の埋め込み方", is_core: true, reached_stage: null },
          ],
          intake: {
            purpose: "基礎知識を身につける",
            source: "",
            prior_knowledge: "",
          },
        }}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "観点ごとの到達度を表示" }),
    );

    const premise = await screen.findByRole("region", { name: "学習の前提" });
    const aspects = screen.getByRole("list", { name: "押さえたい観点" });
    expect(premise.compareDocumentPosition(aspects)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("opens with only the premise when the depth map is missing", async () => {
    render(
      <LearningProgressIndicator
        progress={{
          reached_aspects: [],
          target_count: 3,
          is_complete: false,
          aspects: [],
          intake: { purpose: "", source: "入門書", prior_knowledge: "" },
        }}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "観点ごとの到達度を表示" }),
    );

    expect(
      await screen.findByRole("region", { name: "学習の前提" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("押さえたい観点")).not.toBeInTheDocument();
  });

  it("shows no premise section when every field was skipped", async () => {
    render(
      <LearningProgressIndicator
        progress={{
          reached_aspects: [],
          target_count: 1,
          is_complete: false,
          aspects: [
            { name: "値の埋め込み方", is_core: true, reached_stage: null },
          ],
          intake: null,
        }}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "観点ごとの到達度を表示" }),
    );

    expect(
      await screen.findByRole("list", { name: "押さえたい観点" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "学習の前提" }),
    ).not.toBeInTheDocument();
  });

  it("can be opened from outside", () => {
    render(
      <LearningProgressIndicator
        open
        onOpenChange={() => {}}
        progress={{
          reached_aspects: [],
          target_count: 3,
          is_complete: false,
          intake: { purpose: "仕事で使う", source: "", prior_knowledge: "" },
        }}
      />,
    );

    expect(
      screen.getByRole("region", { name: "学習の前提" }),
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

  it("highlights the trigger while a stage advance is being announced", () => {
    const progress = {
      reached_aspects: [],
      target_count: 1,
      is_complete: false,
      aspects: [
        { name: "A", is_core: true, reached_stage: "defined" as const },
      ],
    };
    const { rerender } = render(
      <LearningProgressIndicator progress={progress} />,
    );
    const trigger = screen.getByRole("button", {
      name: "観点ごとの到達度を表示",
    });
    expect(trigger).not.toHaveAttribute("data-highlighted");

    rerender(<LearningProgressIndicator progress={progress} highlighted />);

    expect(trigger).toHaveAttribute("data-highlighted", "true");
  });
});

describe("LearningProgressIndicator on narrow screens", () => {
  it("hides the word 観点 below md and keeps the bar and the count", () => {
    render(
      <LearningProgressIndicator
        progress={{
          reached_aspects: ["A"],
          target_count: 3,
          is_complete: false,
          aspects: [{ name: "A", is_core: true, reached_stage: "defined" }],
        }}
      />,
    );
    expect(screen.getByText("観点").className).toContain("hidden md:inline");
    expect(screen.getByText("1/3")).toBeInTheDocument();
  });
});

describe("ProgressAdvanceNotice", () => {
  it("announces the notice politely", () => {
    render(
      <ProgressAdvanceNotice notice="値の埋め込み方: なぜ・仕組みまで説明できました" />,
    );

    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent(
      "値の埋め込み方: なぜ・仕組みまで説明できました",
    );
  });

  it("wraps a long notice instead of cutting it off", () => {
    render(
      <ProgressAdvanceNotice notice="とても長い観点の名前: 説明できました" />,
    );

    const chip = screen.getByText("とても長い観点の名前: 説明できました");
    expect(chip.className).not.toMatch(/truncate/);
  });

  it("keeps an empty live region when there is no notice", () => {
    render(<ProgressAdvanceNotice notice={null} />);

    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
});
