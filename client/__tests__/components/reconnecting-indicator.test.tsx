import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReconnectingIndicator } from "@/components/chat/reconnecting-indicator";

describe("ReconnectingIndicator", () => {
  it("announces that the chat is reconnecting", () => {
    render(<ReconnectingIndicator />);

    expect(screen.getByRole("status")).toHaveTextContent("再接続中");
  });
});
