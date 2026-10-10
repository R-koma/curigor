import { beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function CategorySelect() {
  return (
    <Select defaultValue="all">
      <SelectTrigger aria-label="カテゴリー">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">すべて</SelectItem>
        <SelectItem value="os">OS</SelectItem>
      </SelectContent>
    </Select>
  );
}

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

describe("SelectTrigger focus ring", () => {
  it("hides the ring when focus returns after choosing with the pointer", async () => {
    const user = userEvent.setup();
    render(<CategorySelect />);
    const trigger = screen.getByRole("combobox", { name: "カテゴリー" });

    await user.click(trigger);
    await user.click(await screen.findByRole("option", { name: "OS" }));

    await waitFor(() => expect(trigger).toHaveFocus());
    expect(trigger).toHaveAttribute("data-pointer-focus");
  });

  it("brings the ring back on the next key press", async () => {
    const user = userEvent.setup();
    render(<CategorySelect />);
    const trigger = screen.getByRole("combobox", { name: "カテゴリー" });

    await user.click(trigger);
    await user.click(await screen.findByRole("option", { name: "OS" }));
    await waitFor(() => expect(trigger).toHaveAttribute("data-pointer-focus"));

    await user.keyboard("{Shift}");
    expect(trigger).not.toHaveAttribute("data-pointer-focus");
  });

  it("keeps the ring when the choice is made with the keyboard", async () => {
    const user = userEvent.setup();
    render(<CategorySelect />);
    const trigger = screen.getByRole("combobox", { name: "カテゴリー" });

    trigger.focus();
    await user.keyboard("{Enter}");
    await screen.findByRole("option", { name: "OS" });
    await user.keyboard("{ArrowDown}{Enter}");

    await waitFor(() => expect(trigger).toHaveFocus());
    expect(trigger).not.toHaveAttribute("data-pointer-focus");
  });

  it("draws the ring only while the pointer mark is absent", () => {
    render(<CategorySelect />);
    const trigger = screen.getByRole("combobox", { name: "カテゴリー" });
    expect(trigger.className).toContain(
      "focus-visible:not-data-[pointer-focus]:ring-2",
    );
  });
});
