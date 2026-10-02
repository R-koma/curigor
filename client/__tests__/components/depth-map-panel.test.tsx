import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { DepthMapPanel } from "@/components/chat/depth-map-panel";

describe("DepthMapPanel", () => {
  it("lists each aspect with its next-step text and splits non-core aspects", () => {
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

    expect(screen.getByText("1/2")).toBeInTheDocument();
    const core = screen.getByRole("list", { name: "中核の観点" });
    expect(within(core).getByText("値の埋め込み方")).toBeInTheDocument();
    expect(
      within(core).getByText("なぜ・仕組みまで説明できました"),
    ).toBeInTheDocument();
    expect(
      within(core).getByText(
        "次は、なぜ必要か・どう成り立つかを説明してみましょう",
      ),
    ).toBeInTheDocument();
    const related = screen.getByRole("list", { name: "関連する観点" });
    expect(within(related).getByText("文字列の連結")).toBeInTheDocument();
    expect(within(related).getByText("まだ話していません")).toBeInTheDocument();
  });

  it("fills dots up to the reached stage", () => {
    render(
      <DepthMapPanel
        reached={0}
        target={1}
        aspects={[{ name: "A", is_core: true, reached_stage: "defined" }]}
      />,
    );

    expect(screen.getByLabelText("4 段階中 2 段階")).toBeInTheDocument();
  });

  it("omits the related section when every aspect is core", () => {
    render(
      <DepthMapPanel
        reached={0}
        target={1}
        aspects={[{ name: "A", is_core: true, reached_stage: null }]}
      />,
    );

    expect(screen.queryByRole("list", { name: "関連する観点" })).toBeNull();
  });
});
