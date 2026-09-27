import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EndSessionButton } from "@/components/chat/end-session-button";

describe("EndSessionButton", () => {
  it("shows a visible label when highlighted", async () => {
    const onClick = vi.fn();
    render(<EndSessionButton highlighted onClick={onClick} />);

    const button = screen.getByRole("button", { name: "ノートを作成" });
    expect(button).toHaveTextContent("ノートを作成");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is an icon-only button otherwise", async () => {
    const onClick = vi.fn();
    render(<EndSessionButton highlighted={false} onClick={onClick} />);

    const button = screen.getByRole("button", { name: "ノートを作成" });
    expect(button).not.toHaveTextContent("ノートを作成");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });
});
