import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EndSessionButton } from "@/components/chat/end-session-button";

describe("EndSessionButton", () => {
  it("always shows its label", async () => {
    const onClick = vi.fn();
    render(<EndSessionButton label="ノートを更新" onClick={onClick} />);

    const button = screen.getByRole("button", { name: "ノートを更新" });
    expect(button).toHaveTextContent("ノートを更新");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("keeps the label when highlighted", () => {
    render(
      <EndSessionButton label="ノートを作成" highlighted onClick={vi.fn()} />,
    );
    expect(
      screen.getByRole("button", { name: "ノートを作成" }),
    ).toHaveTextContent("ノートを作成");
  });

  it("keeps the label for screen readers but hides it below md when compact", () => {
    render(<EndSessionButton label="ノートを作成" compact onClick={vi.fn()} />);
    const button = screen.getByRole("button", { name: "ノートを作成" });
    const label = screen.getByText("ノートを作成");
    expect(label.className).toContain("sr-only");
    expect(label.className).toContain("md:not-sr-only");
    expect(button).toHaveAttribute("aria-label", "ノートを作成");
  });

  it("shows the label at every width when compact and highlighted", () => {
    render(
      <EndSessionButton
        label="ノートを作成"
        compact
        highlighted
        onClick={vi.fn()}
      />,
    );
    expect(screen.getByText("ノートを作成").className).not.toContain("sr-only");
  });
});
