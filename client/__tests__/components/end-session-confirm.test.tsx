import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EndSessionConfirm } from "@/components/chat/end-session-confirm";

describe("EndSessionConfirm", () => {
  it("offers to create the note and shows the progress", async () => {
    const onEnd = vi.fn();
    render(
      <EndSessionConfirm
        kind="learning"
        createsNote
        progress={{ reached: 3, target: 5 }}
        onEnd={onEnd}
        onContinue={vi.fn()}
      />,
    );
    expect(screen.getByText("説明できた観点 3/5")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "ノートを作成して終了" }),
    );
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it("says no note will be created when nothing was explained", () => {
    render(
      <EndSessionConfirm
        kind="learning"
        createsNote={false}
        onEnd={vi.fn()}
        onContinue={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "ノートを作らずに終了" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/まだ説明が無いため/)).toBeInTheDocument();
  });

  it("uses update wording for a review and shows no progress", () => {
    render(
      <EndSessionConfirm
        kind="review"
        createsNote
        onEnd={vi.fn()}
        onContinue={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "ノートを更新して終了" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/説明できた観点/)).not.toBeInTheDocument();
  });

  it("uses no-update wording for a review without replies", () => {
    render(
      <EndSessionConfirm
        kind="review"
        createsNote={false}
        onEnd={vi.fn()}
        onContinue={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "更新せずに終了" }),
    ).toBeInTheDocument();
  });

  it("continues without ending", async () => {
    const onEnd = vi.fn();
    const onContinue = vi.fn();
    render(
      <EndSessionConfirm
        kind="learning"
        createsNote
        onEnd={onEnd}
        onContinue={onContinue}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "続ける" }));
    expect(onContinue).toHaveBeenCalledOnce();
    expect(onEnd).not.toHaveBeenCalled();
  });

  it("ends only once even when clicked twice", async () => {
    const onEnd = vi.fn();
    render(
      <EndSessionConfirm
        kind="learning"
        createsNote
        onEnd={onEnd}
        onContinue={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", { name: "ノートを作成して終了" });
    await userEvent.dblClick(button);
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it("can end again when the first attempt was not sent", async () => {
    const onEnd = vi.fn().mockReturnValue(false);
    render(
      <EndSessionConfirm
        kind="learning"
        createsNote
        onEnd={onEnd}
        onContinue={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", { name: "ノートを作成して終了" });
    await userEvent.click(button);
    await userEvent.click(button);
    expect(onEnd).toHaveBeenCalledTimes(2);
  });
});
