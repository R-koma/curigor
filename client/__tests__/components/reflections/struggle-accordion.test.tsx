import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StruggleAccordion } from "@/components/reflections/struggle-accordion";

describe("StruggleAccordion", () => {
  it("starts closed and opens on click", async () => {
    render(
      <StruggleAccordion
        variant="struggle"
        items={["なぜ 2 往復では足りないのか"]}
      />,
    );
    const trigger = screen.getByRole("button", {
      name: "うまく説明できなかった所",
    });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("なぜ 2 往復では足りないのか")).toBeVisible();
  });

  it("does not show how many items there are", () => {
    render(<StruggleAccordion variant="struggle" items={["a", "b", "c"]} />);
    expect(screen.getByRole("button")).not.toHaveTextContent(/\d/);
  });

  it("labels questions and shows them as Q and A", async () => {
    render(
      <StruggleAccordion
        variant="question"
        items={[
          { question: "暗反応は暗い所だけ？", answer: "明るくても起きる" },
        ]}
      />,
    );
    const trigger = screen.getByRole("button", { name: "出た疑問" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(trigger);
    expect(screen.getByText("暗反応は暗い所だけ？")).toBeVisible();
    expect(screen.getByText("明るくても起きる")).toBeVisible();
    expect(screen.getByText("Q.")).toBeInTheDocument();
    expect(screen.getByText("A.")).toBeInTheDocument();
  });

  it("renders nothing without items", () => {
    const { container } = render(
      <StruggleAccordion variant="question" items={[]} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
