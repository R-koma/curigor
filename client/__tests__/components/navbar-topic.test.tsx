import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NavbarTopic } from "@/components/chat/navbar-topic";

const LONG_TOPIC =
  "オペレーティングシステムのプロセススケジューリングとコンテキストスイッチの仕組み";

describe("NavbarTopic", () => {
  it("renders the topic without a tooltip or title attribute", () => {
    render(<NavbarTopic topic={LONG_TOPIC} />);

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(LONG_TOPIC);
    expect(heading).not.toHaveAttribute("title");
    expect(heading).not.toHaveAttribute("tabindex");
  });
});
