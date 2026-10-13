import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  ExploreOverviewIndicator,
  ExploreOverviewPanel,
} from "@/components/chat/explore-overview";
import type { ExploreOverview } from "@/lib/explore";

const OVERVIEW: ExploreOverview = {
  aspects: [
    {
      aspect_id: "a1",
      name: "真ん中との比較",
      summary: "真ん中と比べて半分を捨てる",
      is_core: true,
      explained: true,
    },
    {
      aspect_id: "a2",
      name: "計算量",
      summary: "",
      is_core: true,
      explained: false,
    },
    {
      aspect_id: "a3",
      name: "並んでいる前提",
      summary: "並び順が前提になる",
      is_core: false,
      explained: false,
    },
  ],
};

describe("ExploreOverviewPanel", () => {
  it("lists core aspects first with their summaries and marks the explained one", () => {
    render(<ExploreOverviewPanel overview={OVERVIEW} />);

    const core = screen.getByRole("list", { name: "押さえたい観点" });
    expect(core).toHaveTextContent("真ん中との比較");
    expect(core).toHaveTextContent("真ん中と比べて半分を捨てる");
    expect(core).toHaveTextContent("計算量");
    expect(screen.getAllByText("教わった")).toHaveLength(1);
    const related = screen.getByRole("list", { name: "広げられる観点" });
    expect(related).toHaveTextContent("並んでいる前提");
  });

  it("omits the related list when every aspect is core", () => {
    render(
      <ExploreOverviewPanel
        overview={{ aspects: OVERVIEW.aspects.slice(0, 2) }}
      />,
    );

    expect(
      screen.queryByRole("list", { name: "広げられる観点" }),
    ).not.toBeInTheDocument();
  });
});

describe("ExploreOverviewIndicator", () => {
  it("shows how many core aspects were taught and opens the panel", async () => {
    render(<ExploreOverviewIndicator overview={OVERVIEW} />);

    const trigger = screen.getByRole("button", { name: "全体像を表示" });
    expect(trigger).toHaveTextContent("1/2");
    await userEvent.click(trigger);
    expect(
      await screen.findByRole("list", { name: "押さえたい観点" }),
    ).toBeInTheDocument();
  });
});
