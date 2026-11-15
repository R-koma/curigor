import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AskSideButton } from "@/components/chat/side-questions/ask-side-button";

describe("AskSideButton", () => {
  it("calls onClick once when pressed", async () => {
    const onClick = vi.fn();
    render(<AskSideButton onClick={onClick} disabled={false} />);

    await userEvent.click(screen.getByRole("button", { name: "横で質問" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("cannot be pressed while disabled", async () => {
    const onClick = vi.fn();
    render(<AskSideButton onClick={onClick} disabled />);

    const button = screen.getByRole("button", { name: "横で質問" });
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("is hidden below md", () => {
    render(<AskSideButton onClick={() => {}} disabled={false} />);

    expect(screen.getByRole("button", { name: "横で質問" })).toHaveClass(
      "hidden",
      "md:inline-flex",
    );
  });
});
