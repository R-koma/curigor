import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

function ClosingPopover({
  onCloseAutoFocus,
}: {
  onCloseAutoFocus: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger>開く</PopoverTrigger>
      <PopoverContent onCloseAutoFocus={onCloseAutoFocus}>
        <button type="button" onClick={() => setOpen(false)}>
          選ぶ
        </button>
      </PopoverContent>
    </Popover>
  );
}

function renderPopover(onCloseAutoFocus = vi.fn()) {
  render(<ClosingPopover onCloseAutoFocus={onCloseAutoFocus} />);
  return screen.getByRole("button", { name: "開く" });
}

describe("PopoverContent", () => {
  it("does not move focus back to the trigger after choosing inside with the pointer", async () => {
    const trigger = renderPopover();
    await userEvent.click(trigger);
    await userEvent.click(await screen.findByRole("button", { name: "選ぶ" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(trigger).not.toHaveFocus();
  });

  it("moves focus back to the trigger after closing with the keyboard", async () => {
    const trigger = renderPopover();
    trigger.focus();
    await userEvent.keyboard("{Enter}");
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(trigger).toHaveFocus();
  });

  it("still calls the caller's onCloseAutoFocus", async () => {
    const onCloseAutoFocus = vi.fn();
    const trigger = renderPopover(onCloseAutoFocus);
    trigger.focus();
    await userEvent.keyboard("{Enter}");
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(onCloseAutoFocus).toHaveBeenCalledTimes(1));
  });
});
