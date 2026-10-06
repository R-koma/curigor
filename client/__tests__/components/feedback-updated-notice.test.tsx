import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { FeedbackUpdatedNotice } from "@/components/notes/feedback-updated-notice";

describe("FeedbackUpdatedNotice", () => {
  beforeEach(() => {
    window.history.replaceState(
      null,
      "",
      "/notes/n1?feedback=updated#feedback",
    );
  });

  it("announces the update", () => {
    render(<FeedbackUpdatedNotice />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "復習の結果でフィードバックを更新しました",
    );
  });

  it("removes the marker from the URL so a reload does not repeat it", () => {
    render(<FeedbackUpdatedNotice />);
    expect(window.location.search).toBe("");
    expect(window.location.pathname).toBe("/notes/n1");
    expect(window.location.hash).toBe("#feedback");
  });

  it("passes null as the state so Next.js re-attaches its router internals", () => {
    window.history.replaceState(
      { __NA: true },
      "",
      "/notes/n1?feedback=updated#feedback",
    );
    const spy = vi.spyOn(window.history, "replaceState");
    render(<FeedbackUpdatedNotice />);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0]).toBeNull();
    spy.mockRestore();
  });
});
