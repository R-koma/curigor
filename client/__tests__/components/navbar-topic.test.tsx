import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { NavbarTopic } from "@/components/chat/navbar-topic";

const LONG_TOPIC =
  "オペレーティングシステムのプロセススケジューリングとコンテキストスイッチの仕組み";

describe("NavbarTopic", () => {
  it("shows the full topic in a tooltip on keyboard focus", async () => {
    const user = userEvent.setup();
    render(<NavbarTopic topic={LONG_TOPIC} />);

    await user.tab();

    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
    expect(await screen.findByRole("tooltip")).toHaveTextContent(LONG_TOPIC);
  });

  it("does not use the title attribute", () => {
    render(<NavbarTopic topic={LONG_TOPIC} />);

    expect(screen.getByRole("heading", { level: 1 })).not.toHaveAttribute(
      "title",
    );
  });
});
