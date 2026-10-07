import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SessionEndedNotice } from "@/components/chat/session-ended-notice";

describe("SessionEndedNotice", () => {
  it("explains why no note was created", () => {
    render(<SessionEndedNotice kind="learning" noteSkipped />);
    expect(
      screen.getByText("説明がまだ無かったため、ノートは作成しませんでした"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "ダッシュボードに戻る" }),
    ).toHaveAttribute("href", "/dashboard");
  });

  it("explains why the review did not update the note", () => {
    render(<SessionEndedNotice kind="review" noteSkipped />);
    expect(
      screen.getByText("返答が無かったため、ノートは更新しませんでした"),
    ).toBeInTheDocument();
  });

  it("falls back to the plain ended message", () => {
    render(<SessionEndedNotice kind="learning" noteSkipped={false} />);
    expect(screen.getByText("セッションが終了しました")).toBeInTheDocument();
  });
});
