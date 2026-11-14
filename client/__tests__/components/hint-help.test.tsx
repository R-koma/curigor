import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HintHelp } from "@/components/hints/hint-help";
import { HINT_GUIDE } from "@/lib/hints";

describe("HintHelp", () => {
  it("shows the hint guides in order when the button is pressed", async () => {
    render(<HintHelp ids={["chat_input", "end_session"]} />);
    expect(screen.queryByText(HINT_GUIDE.chat_input.title)).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "使い方を見る" }));

    const dialog = await screen.findByRole("dialog", { name: "使い方" });
    const items = dialog.querySelectorAll("li");
    expect([...items].map((li) => li.textContent)).toEqual([
      HINT_GUIDE.chat_input.title + HINT_GUIDE.chat_input.body,
      HINT_GUIDE.end_session.title + HINT_GUIDE.end_session.body,
    ]);
  });

  it("is available without the hints provider, even after the bands were dismissed", async () => {
    render(<HintHelp ids={["note_detail"]} />);
    await userEvent.click(screen.getByRole("button", { name: "使い方を見る" }));
    expect(
      await screen.findByText(HINT_GUIDE.note_detail.title),
    ).toBeInTheDocument();
  });

  it("shows each item as a heading line and a one-line body, with the icon hidden from assistive tech", async () => {
    render(<HintHelp ids={["chat_input"]} />);
    await userEvent.click(screen.getByRole("button", { name: "使い方を見る" }));
    const dialog = await screen.findByRole("dialog", { name: "使い方" });

    expect(screen.getByText(HINT_GUIDE.chat_input.title)).toHaveClass(
      "font-semibold",
    );
    const icon = dialog.querySelector("li svg");
    expect(icon).not.toBeNull();
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });

  it("closes with Escape", async () => {
    render(<HintHelp ids={["learn_start"]} />);
    await userEvent.click(screen.getByRole("button", { name: "使い方を見る" }));
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("HINT_GUIDE", () => {
  it("never points at a position in the guide copy", () => {
    for (const guide of Object.values(HINT_GUIDE)) {
      expect(guide.title).not.toContain("上の");
      expect(guide.body).not.toContain("上の");
    }
  });
});
