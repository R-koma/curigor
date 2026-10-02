import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { DepthMapPanel } from "@/components/chat/depth-map-panel";

describe("DepthMapPanel", () => {
  it("groups aspects under plain-language headings with a stage chip and next step", () => {
    render(
      <DepthMapPanel
        reached={1}
        target={2}
        aspects={[
          { name: "値の埋め込み方", is_core: true, reached_stage: "reasoned" },
          { name: "値の指定と再利用", is_core: true, reached_stage: "defined" },
          { name: "文字列の連結", is_core: false, reached_stage: null },
        ]}
      />,
    );

    expect(screen.getByText("1/2 達成")).toBeInTheDocument();
    const core = screen.getByRole("list", { name: "押さえたい観点" });
    expect(within(core).getByText("値の埋め込み方")).toBeInTheDocument();
    expect(within(core).getByText("なぜ・仕組み")).toBeInTheDocument();
    expect(within(core).getByText("定義")).toBeInTheDocument();
    expect(
      within(core).getByText("なぜ・仕組みまで説明できました"),
    ).toBeInTheDocument();
    expect(
      within(core).getByText(
        "次は、なぜ必要か・どう成り立つかを説明してみましょう",
      ),
    ).toBeInTheDocument();
    const related = screen.getByRole("list", { name: "広げられる観点" });
    expect(within(related).getByText("文字列の連結")).toBeInTheDocument();
    expect(within(related).getByText("まだ話していません")).toBeInTheDocument();
  });

  it("no longer uses the word 中核 anywhere", () => {
    render(
      <DepthMapPanel
        reached={0}
        target={1}
        aspects={[{ name: "A", is_core: true, reached_stage: null }]}
      />,
    );

    expect(screen.queryByText(/中核/)).toBeNull();
  });

  it("describes the stage bar by how many of the four stages are reached", () => {
    render(
      <DepthMapPanel
        reached={0}
        target={1}
        aspects={[{ name: "A", is_core: true, reached_stage: "defined" }]}
      />,
    );

    expect(screen.getByLabelText("4 段階中 2 段階")).toBeInTheDocument();
  });

  it("marks an aspect as achieved once it reaches the why/how stage", () => {
    render(
      <DepthMapPanel
        reached={1}
        target={2}
        aspects={[
          { name: "達成済み", is_core: true, reached_stage: "reasoned" },
          { name: "途中", is_core: true, reached_stage: "defined" },
        ]}
      />,
    );

    expect(screen.getAllByLabelText("達成")).toHaveLength(1);
  });

  it("omits the related section when every aspect is a main one", () => {
    render(
      <DepthMapPanel
        reached={0}
        target={1}
        aspects={[{ name: "A", is_core: true, reached_stage: null }]}
      />,
    );

    expect(screen.queryByRole("list", { name: "広げられる観点" })).toBeNull();
  });
});
