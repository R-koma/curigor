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
