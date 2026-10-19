import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  it("keeps the learning premise folded under the aspects", async () => {
    render(<NoteAspectMap aspectMap={ASPECT_MAP} intake={INTAKE} />);

    expect(screen.getByText("基礎知識を身につける")).not.toBeVisible();
    await userEvent.click(screen.getByText("学習の前提"));
    expect(screen.getByText("基礎知識を身につける")).toBeVisible();
    expect(screen.getByText("入門書")).toBeVisible();
    expect(screen.getByText("初めて学ぶ")).toBeVisible();
    expect(screen.getByText("プロセス")).toBeVisible();
  });

  it("omits the rows that were not answered", () => {
    render(
      <NoteAspectMap
        aspectMap={ASPECT_MAP}
        intake={{ purpose: "", source: "入門書", prior_knowledge: "" }}
      />,
    );

    expect(screen.getByText("教材")).toBeInTheDocument();
    expect(screen.queryByText("目的")).not.toBeInTheDocument();
    expect(screen.queryByText("今の理解")).not.toBeInTheDocument();
  });

  it.each([
    ["null", null],
    ["undefined", undefined],
  ])("shows no premise when intake is %s", (_, intake) => {
    render(<NoteAspectMap aspectMap={ASPECT_MAP} intake={intake} />);

    expect(screen.queryByText("学習の前提")).not.toBeInTheDocument();
    expect(screen.getByText("プロセス")).toBeVisible();
  });

  it("renders nothing when there are no aspects, even with a premise", () => {
    const { container } = render(
      <NoteAspectMap aspectMap={{ root: "OS", aspects: [] }} intake={INTAKE} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("shows aspect names and keeps each summary folded until opened", async () => {
    render(<NoteAspectMap aspectMap={ASPECT_MAP} />);

    expect(screen.getByText("プロセス")).toBeVisible();
    expect(screen.getByText("実行中のプログラム")).not.toBeVisible();
    await userEvent.click(screen.getByText("プロセス"));
    expect(screen.getByText("実行中のプログラム")).toBeVisible();
  });

  it("names the coverage once in the overview with counts, and on each icon", () => {
    render(
      <NoteAspectMap
        aspectMap={{
          root: "OS",
          aspects: [
            {
              name: "プロセス",
              summary: "",
              coverage: "covered",
              children: [{ name: "PCB", summary: "", coverage: "uncovered" }],
            },
            { name: "スレッド", summary: "", coverage: "partial" },
          ],
        }}
      />,
    );

    expect(screen.getByText("説明できた").parentElement).toHaveTextContent(
      "説明できた1",
    );
    expect(
      screen.getByText("まだ触れていない").parentElement,
    ).toHaveTextContent("まだ触れていない1");
    expect(screen.getByRole("img", { name: "一部だけ" })).toBeInTheDocument();
  });

  it("anchors each aspect that has an id so feedback can link to it", () => {
    const { container } = render(
      <NoteAspectMap
        aspectMap={{
          root: "OS",
          aspects: [
            { id: "a1", name: "プロセス", summary: "", coverage: "covered" },
            { name: "スレッド", summary: "", coverage: "partial" },
          ],
        }}
      />,
    );
    expect(container.querySelector("#aspect-a1")).toHaveTextContent("プロセス");
    expect(container.querySelectorAll("[id^='aspect-a']")).toHaveLength(1);
  });
});
