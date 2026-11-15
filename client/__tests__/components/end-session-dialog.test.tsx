import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EndSessionDialog } from "@/components/chat/end-session-dialog";
import { DESKTOP_WIDTH, setMediaQuery } from "../stubs/match-media";

function setup(
  props: Partial<React.ComponentProps<typeof EndSessionDialog>> = {},
) {
  const handlers = {
    onOpenChange: vi.fn(),
    onEnd: vi.fn(),
    onSave: vi.fn(),
    onDiscard: vi.fn().mockResolvedValue(undefined),
  };
  render(
    <EndSessionDialog
      open
      kind="learning"
      topic="TCP の輻輳制御"
      progress={null}
      {...handlers}
      {...props}
    />,
  );
  return handlers;
}

describe("EndSessionDialog", () => {
  beforeEach(() => setMediaQuery(DESKTOP_WIDTH, true));

  it("shows the learning choices with checks before crosses", () => {
    setup();
    expect(screen.getByText("セッションをどうしますか？")).toBeInTheDocument();
    expect(screen.getByText("TCP の輻輳制御")).toBeInTheDocument();
    expect(screen.getByText("学び終えたとき")).toBeInTheDocument();
    expect(screen.getByText("終了してノートを作成")).toBeInTheDocument();
    expect(screen.getByText("まだ途中のとき")).toBeInTheDocument();
    expect(screen.getByText("保存して後で続ける")).toBeInTheDocument();
    const marks = screen
      .getAllByTestId("point-mark")
      .map((el) => el.textContent);
    expect(marks).toEqual(["✓", "✓", "✓", "✓", "✕", "✕"]);
    expect(
      screen.getByText("復習の予定に入り、日をおいて思い出す練習をします"),
    ).toBeInTheDocument();
    expect(screen.getByText("復習の予定には入りません")).toBeInTheDocument();
  });

  it("switches wording for a review", () => {
    setup({ kind: "review" });
    expect(screen.getByText("終了してノートを更新")).toBeInTheDocument();
    expect(screen.getByText("次の復習日が決まります")).toBeInTheDocument();
    expect(
      screen.getByText("次の復習日はまだ変わりません"),
    ).toBeInTheDocument();
  });

  it("switches wording for an explore session", () => {
    setup({ kind: "explore" });
    expect(screen.getByText("終了して学習メモを作成")).toBeInTheDocument();
    expect(screen.getByText("学習メモを作ります")).toBeInTheDocument();
    expect(screen.getByText("学習メモはまだ作りません")).toBeInTheDocument();
    expect(screen.getAllByTestId("point-mark")).toHaveLength(4);
  });

  it("ends and saves from the two choices", async () => {
    const h = setup();
    await userEvent.click(
      screen.getByRole("button", { name: /終了してノートを作成/ }),
    );
    expect(h.onEnd).toHaveBeenCalledOnce();
    await userEvent.click(
      screen.getByRole("button", { name: /保存して後で続ける/ }),
    );
    expect(h.onSave).toHaveBeenCalledOnce();
  });

  it("asks again before discarding, and can go back", async () => {
    const h = setup();
    await userEvent.click(
      screen.getByRole("button", { name: "保存せずに捨てる" }),
    );
    expect(
      screen.getByText("この会話を消します。元に戻せません"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "やめる" }));
    expect(h.onDiscard).not.toHaveBeenCalled();
    expect(screen.getByText("学び終えたとき")).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "保存せずに捨てる" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "捨てる" }));
    expect(h.onDiscard).toHaveBeenCalledOnce();
  });

  it("closes through cancel", async () => {
    const h = setup();
    await userEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(h.onOpenChange).toHaveBeenCalledWith(false);
  });

  it("shows the progress only when given", () => {
    setup({ progress: { reached: 2, target: 5 } });
    expect(screen.getByText("説明できた観点 2 / 5")).toBeInTheDocument();
  });

  it("hides the progress when null", () => {
    setup();
    expect(screen.queryByText(/説明できた観点/)).not.toBeInTheDocument();
  });

  it("renders a bottom sheet below md", () => {
    setMediaQuery(DESKTOP_WIDTH, false);
    setup();
    const dialog = screen.getByRole("dialog");
    expect(dialog.className).toContain("slide-in-from-bottom");
    expect(
      within(dialog).getByText("セッションをどうしますか？"),
    ).toBeInTheDocument();
  });
});
