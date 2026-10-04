import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IntakeAnsweredNotice } from "@/components/chat/intake-answered-notice";

describe("IntakeAnsweredNotice", () => {
  it("opens the depth map from the notice", async () => {
    const onOpenPanel = vi.fn();
    render(<IntakeAnsweredNotice onOpenPanel={onOpenPanel} />);

    expect(screen.getByText("学習の前提を回答しました")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "観点マップで確認" }),
    );

    expect(onOpenPanel).toHaveBeenCalledOnce();
  });

  it("has no button while there is no panel to open", () => {
    render(<IntakeAnsweredNotice />);

    expect(screen.getByText("学習の前提を回答しました")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
