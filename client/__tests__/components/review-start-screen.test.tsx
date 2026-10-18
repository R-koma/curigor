import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewStartScreen } from "@/components/review/review-start-screen";

function renderScreen(
  props: Partial<Parameters<typeof ReviewStartScreen>[0]> = {},
) {
  const onStart = vi.fn();
  render(
    <ReviewStartScreen
      noteId="n1"
      topic="二分探索"
      summary="探索範囲を半分に絞る"
      focusCount={2}
      focusAspects={[]}
      onStart={onStart}
      {...props}
    />,
  );
  return { onStart };
}

describe("ReviewStartScreen", () => {
  it("shows how many prior improvements this review focuses on", () => {
    renderScreen();
    expect(
      screen.getByRole("heading", { name: "今回の重点" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("前回の改善点 2 件も、復習の中で確かめます。"),
    ).toBeInTheDocument();
  });

  it.each([0, null])("hides the focus when the count is %s", (focusCount) => {
    renderScreen({ focusCount });
    expect(
      screen.queryByRole("heading", { name: "今回の重点" }),
    ).not.toBeInTheDocument();
  });

  it("hides the summary section when the summary is empty", () => {
    renderScreen({ summary: "" });
    expect(
      screen.queryByRole("heading", { name: "前回の要約" }),
    ).not.toBeInTheDocument();
  });

  it("starts the review", async () => {
    const { onStart } = renderScreen();
    await userEvent.click(
      screen.getByRole("button", { name: "復習を開始する" }),
    );
    expect(onStart).toHaveBeenCalledOnce();
  });
});

describe("ReviewStartScreen focus aspects", () => {
  const ASPECTS = [
    { id: "a1", name: "計算量" },
    { id: "a2", name: "前提条件" },
  ];

  it("lists every top-level aspect of the note", () => {
    renderScreen({ focusAspects: ASPECTS });
    expect(screen.getByRole("button", { name: "計算量" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "前提条件" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("優先して確かめたい観点を選べます。"),
    ).toBeInTheDocument();
  });

  it("starts with no aspect selected and sends null", async () => {
    const { onStart } = renderScreen({ focusAspects: ASPECTS });
    expect(screen.getByRole("button", { name: "計算量" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "復習を開始する" }),
    );
    expect(onStart).toHaveBeenCalledWith(null);
  });

  it("sends only the aspects the user selected", async () => {
    const { onStart } = renderScreen({ focusAspects: ASPECTS });
    const toggle = screen.getByRole("button", { name: "前提条件" });
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(
      screen.getByRole("button", { name: "復習を開始する" }),
    );
    expect(onStart).toHaveBeenCalledWith(["a2"]);
  });

  it("sends null again after a selection is cleared", async () => {
    const { onStart } = renderScreen({ focusAspects: ASPECTS });
    const toggle = screen.getByRole("button", { name: "計算量" });
    await userEvent.click(toggle);
    await userEvent.click(toggle);
    await userEvent.click(
      screen.getByRole("button", { name: "復習を開始する" }),
    );
    expect(onStart).toHaveBeenCalledWith(null);
  });

  it("offers aspects to choose even when the improvement count is unknown", () => {
    renderScreen({ focusCount: null, focusAspects: ASPECTS });
    expect(screen.getByRole("button", { name: "計算量" })).toBeInTheDocument();
  });
});

describe("ReviewStartScreen memo aspects", () => {
  const ASPECTS = [
    { id: "a1", name: "計算量" },
    { id: "a2", name: "前提条件" },
  ];

  it("marks memo aspects with 学習メモあり・先に聞きます whether or not they are selected", async () => {
    renderScreen({ focusAspects: ASPECTS, memoAspectIds: new Set(["a1"]) });

    expect(screen.getAllByText("学習メモあり・先に聞きます")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "前提条件" }));
    expect(screen.getAllByText("学習メモあり・先に聞きます")).toHaveLength(1);
  });

  it("marks a top-level aspect when the memo points at one of its children", () => {
    renderScreen({ focusAspects: ASPECTS, memoAspectIds: new Set(["a2-1"]) });
    const marks = screen.getAllByText("学習メモあり・先に聞きます");
    expect(marks).toHaveLength(1);
    expect(marks[0].closest("li")).toHaveTextContent("前提条件");
  });

  it("shows no mark without memo aspects", () => {
    renderScreen({ focusAspects: ASPECTS });
    expect(
      screen.queryByText("学習メモあり・先に聞きます"),
    ).not.toBeInTheDocument();
  });
});
