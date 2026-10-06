import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { MessageActionButton } from "@/components/chat/message-action-button";

describe("MessageActionButton", () => {
  it("has the label as its accessible name", () => {
    render(<MessageActionButton label="編集して再送信">x</MessageActionButton>);

    expect(
      screen.getByRole("button", { name: "編集して再送信" }),
    ).toBeInTheDocument();
  });

  it("is revealed by keyboard focus, not only by hovering the message", () => {
    render(<MessageActionButton label="コピー">x</MessageActionButton>);

    const button = screen.getByRole("button", { name: "コピー" });
    expect(button).toHaveClass("group-hover:opacity-100");
    expect(button).toHaveClass("group-focus-within:opacity-100");
    expect(button).toHaveClass("focus-visible:opacity-100");
  });

  it("stays visible when asked to", () => {
    render(
      <MessageActionButton label="停止" alwaysVisible>
        x
      </MessageActionButton>,
    );

    expect(screen.getByRole("button", { name: "停止" })).toHaveClass(
      "opacity-100",
    );
  });

  it("shows the label as a tooltip on keyboard focus", async () => {
    render(<MessageActionButton label="コピー">x</MessageActionButton>);

    await userEvent.tab();

    expect(await screen.findByRole("tooltip")).toHaveTextContent("コピー");
  });
});
