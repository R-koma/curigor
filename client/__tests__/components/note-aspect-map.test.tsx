import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import {
  NoteAspectMap,
  type AspectMap,
} from "@/components/notes/note-aspect-map";

const ASPECT_MAP: AspectMap = {
  root: "OS",
  aspects: [
    {
      name: "プロセス",
      summary: "実行中のプログラム",
      coverage: "covered",
    },
  ],
};

const INTAKE = {
  purpose: "基礎知識を身につける",
  source: "入門書",
  prior_knowledge: "初めて学ぶ",
};

describe("NoteAspectMap", () => {
  it("shows the learning premise above the aspects", () => {
    render(<NoteAspectMap aspectMap={ASPECT_MAP} intake={INTAKE} />);

    const premise = screen.getByRole("region", { name: "学習の前提" });
    expect(within(premise).getByText("基礎知識を身につける")).toBeVisible();
    expect(within(premise).getByText("入門書")).toBeVisible();
    expect(within(premise).getByText("初めて学ぶ")).toBeVisible();
    expect(screen.getByText("プロセス")).toBeVisible();
  });

  it("omits the rows that were not answered", () => {
    render(
      <NoteAspectMap
        aspectMap={ASPECT_MAP}
        intake={{ purpose: "", source: "入門書", prior_knowledge: "" }}
      />,
    );

    const premise = screen.getByRole("region", { name: "学習の前提" });
    expect(within(premise).getByText("教材")).toBeInTheDocument();
    expect(within(premise).queryByText("目的")).not.toBeInTheDocument();
    expect(within(premise).queryByText("今の理解")).not.toBeInTheDocument();
  });

  it.each([
    ["null", null],
    ["undefined", undefined],
  ])("shows no premise section when intake is %s", (_, intake) => {
    render(<NoteAspectMap aspectMap={ASPECT_MAP} intake={intake} />);

    expect(
      screen.queryByRole("region", { name: "学習の前提" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("プロセス")).toBeVisible();
  });

  it("renders nothing when there are no aspects, even with a premise", () => {
    const { container } = render(
      <NoteAspectMap aspectMap={{ root: "OS", aspects: [] }} intake={INTAKE} />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
