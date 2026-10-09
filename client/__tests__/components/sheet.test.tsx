import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

function Harness() {
  return (
    <Sheet>
      <SheetTrigger>開く</SheetTrigger>
      <SheetContent>
        <SheetTitle>メニュー</SheetTitle>
        <p>中身</p>
      </SheetContent>
    </Sheet>
  );
}

describe("Sheet", () => {
  it("opens as a named dialog and closes with the close button", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "開く" }));
    expect(
      await screen.findByRole("dialog", { name: "メニュー" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "閉じる" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("closes with Escape and returns focus to the trigger", async () => {
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "開く" });
    await userEvent.click(trigger);
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("hides the overlay and the panel on wide screens", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "開く" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.className).toContain("md:hidden");
    const overlay = document.querySelector('[data-slot="sheet-overlay"]');
    expect(overlay?.className).toContain("md:hidden");
  });

  it("keeps the close button for keyboards and screen readers but does not draw it", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "開く" }));
    await screen.findByRole("dialog");
    expect(screen.getByRole("button", { name: "閉じる" }).className).toContain(
      "sr-only",
    );
  });

  it("leaves a wide strip of the page uncovered so it can be tapped to close", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "開く" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.className).toContain("w-[min(75vw,18rem)]");
  });
});
