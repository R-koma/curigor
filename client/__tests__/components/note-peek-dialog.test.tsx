import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NotePeekDialog } from "@/components/review/note-peek-dialog";

describe("NotePeekDialog", () => {
  it("shows the note with a prompt to explain after closing", () => {
    render(<NotePeekDialog open content="## 計算量" onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "ノート" })).toBeInTheDocument();
    expect(
      screen.getByText("読んだら閉じて、自分の言葉で説明してみましょう"),
    ).toBeInTheDocument();
    expect(screen.getByText("計算量")).toBeInTheDocument();
  });

  it("calls onClose once when closed to explain", async () => {
    const onClose = vi.fn();
    render(<NotePeekDialog open content="本文" onClose={onClose} />);
    await userEvent.click(
      screen.getByRole("button", { name: "閉じて説明する" }),
    );
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when dismissed with Escape", async () => {
    const onClose = vi.fn();
    render(<NotePeekDialog open content="本文" onClose={onClose} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
