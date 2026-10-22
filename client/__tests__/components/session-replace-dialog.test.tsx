import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionReplaceDialog } from "@/components/chat/session-replace-dialog";
import { useSessionReplaceConfirm } from "@/hooks/use-session-replace-confirm";
import type { ActiveSession } from "@/lib/active-session";

const fetchActiveSession = vi.fn();
vi.mock("@/lib/active-session", () => ({
  fetchActiveSession: () => fetchActiveSession(),
}));

const review: ActiveSession = {
  session_id: "s1",
  session_type: "review",
  status: "in_progress",
  started_at: "2026-10-19T12:13:13Z",
  topic: "元号の歴史",
  note_id: "n1",
};

function Harness({
  start,
  onCancel,
}: {
  start: () => void;
  onCancel: () => void;
}) {
  const { pendingSession, confirmStart, confirm, cancel } =
    useSessionReplaceConfirm();
  return (
    <>
      <button type="button" onClick={() => void confirmStart(start, onCancel)}>
        始める
      </button>
      <SessionReplaceDialog
        session={pendingSession}
        onConfirm={confirm}
        onCancel={cancel}
      />
    </>
  );
}

function setup() {
  const start = vi.fn();
  const onCancel = vi.fn();
  render(<Harness start={start} onCancel={onCancel} />);
  return { start, onCancel };
}

describe("進行中のセッションを終える確認", () => {
  beforeEach(() => {
    fetchActiveSession.mockReset();
  });

  it("進行中のセッションが無ければ確認せずに始める", async () => {
    fetchActiveSession.mockResolvedValue(null);
    const { start } = setup();
    await userEvent.click(screen.getByRole("button", { name: "始める" }));
    expect(start).toHaveBeenCalledOnce();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("進行中のセッションを確認できなければ確認せずに始める", async () => {
    fetchActiveSession.mockRejectedValue(new Error("network"));
    const { start } = setup();
    await userEvent.click(screen.getByRole("button", { name: "始める" }));
    expect(start).toHaveBeenCalledOnce();
  });

  it("進行中のセッションがあれば、その種類とトピックを示して確かめる", async () => {
    fetchActiveSession.mockResolvedValue(review);
    const { start } = setup();
    await userEvent.click(screen.getByRole("button", { name: "始める" }));
    expect(await screen.findByRole("alertdialog")).toHaveTextContent(
      "進行中の「元号の歴史」（復習）は終了し、続きから再開できなくなります。",
    );
    expect(start).not.toHaveBeenCalled();
  });

  it("終了して始めると一度だけ始め、キャンセルの処理は呼ばない", async () => {
    fetchActiveSession.mockResolvedValue(review);
    const { start, onCancel } = setup();
    await userEvent.click(screen.getByRole("button", { name: "始める" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "終了して始める" }),
    );
    expect(start).toHaveBeenCalledOnce();
    expect(onCancel).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("キャンセルすると始めない", async () => {
    fetchActiveSession.mockResolvedValue(review);
    const { start, onCancel } = setup();
    await userEvent.click(screen.getByRole("button", { name: "始める" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "キャンセル" }),
    );
    expect(start).not.toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("確かめているあいだに押し直しても一度しか始めない", async () => {
    let resolve!: (session: ActiveSession | null) => void;
    fetchActiveSession.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    const { start } = setup();
    const button = screen.getByRole("button", { name: "始める" });
    await userEvent.click(button);
    await userEvent.click(button);
    resolve(null);
    await vi.waitFor(() => expect(start).toHaveBeenCalledOnce());
    expect(fetchActiveSession).toHaveBeenCalledOnce();
  });

  it("トピックが無いセッションは種類だけで示す", async () => {
    fetchActiveSession.mockResolvedValue({
      ...review,
      session_type: "explore",
      topic: null,
    });
    setup();
    await userEvent.click(screen.getByRole("button", { name: "始める" }));
    expect(await screen.findByRole("alertdialog")).toHaveTextContent(
      "進行中のセッション（理解する）は終了し",
    );
  });
});
