import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StartModeToggle } from "@/components/chat/start-mode-toggle";

describe("StartModeToggle", () => {
  it("marks the current mode", () => {
    render(<StartModeToggle explore={false} onChange={vi.fn()} />);

    expect(screen.getByRole("radio", { name: /説明して学ぶ/ })).toBeChecked();
    expect(
      screen.getByRole("radio", { name: /教わってから始める/ }),
    ).not.toBeChecked();
  });

  it("switches to explore and back", async () => {
    const onChange = vi.fn();
    render(<StartModeToggle explore={false} onChange={onChange} />);

    await userEvent.click(
      screen.getByRole("radio", { name: /教わってから始める/ }),
    );
    expect(onChange).toHaveBeenLastCalledWith(true);

    await userEvent.click(screen.getByRole("radio", { name: /説明して学ぶ/ }));
    expect(onChange).toHaveBeenLastCalledWith(false);
  });
});
