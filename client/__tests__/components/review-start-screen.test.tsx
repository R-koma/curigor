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
    expect(screen.getByText(/前回の改善点 2 件/)).toBeInTheDocument();
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
    { id: "a1", name: "計算量", count: 1 },
    { id: "a2", name: "前提条件", count: 1 },
  ];

  it("starts with every focus aspect selected", async () => {
    const { onStart } = renderScreen({ focusAspects: ASPECTS });
    await userEvent.click(
      screen.getByRole("button", { name: "復習を開始する" }),
    );
    expect(onStart).toHaveBeenCalledWith(["a1", "a2"]);
  });

  it("sends only the aspects left selected", async () => {
    const { onStart } = renderScreen({ focusAspects: ASPECTS });
    const toggle = screen.getByRole("button", { name: "計算量" });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(
      screen.getByRole("button", { name: "復習を開始する" }),
    );
    expect(onStart).toHaveBeenCalledWith(["a2"]);
  });

  it("sends an empty selection when every aspect is turned off", async () => {
    const { onStart } = renderScreen({ focusAspects: ASPECTS });
    await userEvent.click(screen.getByRole("button", { name: "計算量" }));
    await userEvent.click(screen.getByRole("button", { name: "前提条件" }));
    await userEvent.click(
      screen.getByRole("button", { name: "復習を開始する" }),
    );
    expect(onStart).toHaveBeenCalledWith([]);
  });

  it("lowers the improvement count when an aspect is turned off", async () => {
    renderScreen({
      focusCount: 4,
      focusAspects: [
        { id: "a1", name: "計算量", count: 2 },
        { id: "a2", name: "前提条件", count: 1 },
      ],
    });
    expect(screen.getByText(/前回の改善点 4 件/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "計算量" }));
    expect(screen.getByText(/前回の改善点 2 件/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "計算量" }));
    expect(screen.getByText(/前回の改善点 4 件/)).toBeInTheDocument();
  });

  it("sends null when no aspect is offered", async () => {
    const { onStart } = renderScreen({ focusAspects: [] });
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
