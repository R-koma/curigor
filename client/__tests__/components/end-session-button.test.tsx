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
});
