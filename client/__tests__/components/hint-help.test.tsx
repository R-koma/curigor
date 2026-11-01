import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HintHelp } from "@/components/hints/hint-help";
import { HINT_TEXT } from "@/lib/hints";

describe("HintHelp", () => {
  it("shows the hint texts in order when the button is pressed", async () => {
    render(<HintHelp ids={["chat_input", "end_session"]} />);
    expect(screen.queryByText(HINT_TEXT.chat_input)).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "使い方を見る" }));

    const dialog = await screen.findByRole("dialog", { name: "使い方" });
    const items = dialog.querySelectorAll("li");
    expect([...items].map((li) => li.textContent)).toEqual([
      HINT_TEXT.chat_input,
      HINT_TEXT.end_session,
    ]);
  });

  it("is available without the hints provider, even after the bands were dismissed", async () => {
    render(<HintHelp ids={["note_detail"]} />);
    await userEvent.click(screen.getByRole("button", { name: "使い方を見る" }));
    expect(await screen.findByText(HINT_TEXT.note_detail)).toBeInTheDocument();
  });

  it("closes with Escape", async () => {
    render(<HintHelp ids={["learn_start"]} />);
    await userEvent.click(screen.getByRole("button", { name: "使い方を見る" }));
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
