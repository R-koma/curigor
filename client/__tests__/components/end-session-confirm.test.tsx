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
        onSave={vi.fn()}
        onDiscard={vi.fn()}
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
        onSave={vi.fn()}
        onDiscard={vi.fn()}
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
        onSave={vi.fn()}
        onDiscard={vi.fn()}
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
        onSave={vi.fn()}
        onDiscard={vi.fn()}
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
        onSave={vi.fn()}
        onDiscard={vi.fn()}
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
        onSave={vi.fn()}
        onDiscard={vi.fn()}
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
        onSave={vi.fn()}
        onDiscard={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", { name: "ノートを作成して終了" });
    await userEvent.click(button);
    await userEvent.click(button);
    expect(onEnd).toHaveBeenCalledTimes(2);
  });

  it("uses study memo wording for an explore session", async () => {
    const onEnd = vi.fn();
    render(
      <EndSessionConfirm
        kind="explore"
        createsNote
        onEnd={onEnd}
        onContinue={vi.fn()}
        onSave={vi.fn()}
        onDiscard={vi.fn()}
      />,
    );

    expect(screen.queryByText(/観点/)).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "学習メモを作成して終了" }),
    );
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it("says no study memo will be created when nothing was taught", () => {
    render(
      <EndSessionConfirm
        kind="explore"
        createsNote={false}
        onEnd={vi.fn()}
        onContinue={vi.fn()}
        onSave={vi.fn()}
        onDiscard={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "学習メモを作らずに終了" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/まだ教わった内容が無いため/)).toBeInTheDocument();
  });

  it("offers save and discard, asking again before discarding", async () => {
    const onSave = vi.fn();
    const onDiscard = vi.fn().mockResolvedValue(undefined);
    render(
      <EndSessionConfirm
        kind="learning"
        createsNote
        onEnd={vi.fn()}
        onContinue={vi.fn()}
        onSave={onSave}
        onDiscard={onDiscard}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "保存して後で続ける" }),
    );
    expect(onSave).toHaveBeenCalledOnce();

    await userEvent.click(
      screen.getByRole("button", { name: "保存せずに捨てる" }),
    );
    expect(onDiscard).not.toHaveBeenCalled();
    expect(
      screen.getByText("この会話を消します。元に戻せません"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "捨てる" }));
    expect(onDiscard).toHaveBeenCalledOnce();
  });

  it("goes back from the discard confirmation without discarding", async () => {
    const onDiscard = vi.fn();
    render(
      <EndSessionConfirm
        kind="learning"
        createsNote
        onEnd={vi.fn()}
        onContinue={vi.fn()}
        onSave={vi.fn()}
        onDiscard={onDiscard}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "保存せずに捨てる" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "やめる" }));
    expect(onDiscard).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "保存して後で続ける" }),
    ).toBeInTheDocument();
  });
});
