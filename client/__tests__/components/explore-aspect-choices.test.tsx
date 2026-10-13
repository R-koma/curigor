import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ExploreAspectChoices } from "@/components/chat/explore-aspect-choices";
import type { ExploreOverview } from "@/lib/explore";

const OVERVIEW: ExploreOverview = {
  aspects: [
    {
      aspect_id: "a1",
      name: "真ん中との比較",
      summary: "",
      is_core: true,
      explained: false,
    },
    {
      aspect_id: "a2",
      name: "計算量",
      summary: "",
      is_core: true,
      explained: false,
    },
  ],
};

describe("ExploreAspectChoices", () => {
  it("starts from the beginning", async () => {
    const onChoose = vi.fn();
    render(<ExploreAspectChoices overview={OVERVIEW} onChoose={onChoose} />);

    await userEvent.click(screen.getByRole("button", { name: "最初から" }));

    expect(onChoose).toHaveBeenCalledWith("最初から");
  });

  it("asks to be taught the chosen aspect", async () => {
    const onChoose = vi.fn();
    render(<ExploreAspectChoices overview={OVERVIEW} onChoose={onChoose} />);

    await userEvent.click(screen.getByRole("button", { name: "計算量" }));

    expect(onChoose).toHaveBeenCalledWith("「計算量」から教えてください");
  });

  it("disables every button while disabled", () => {
    render(
      <ExploreAspectChoices overview={OVERVIEW} disabled onChoose={vi.fn()} />,
    );

    for (const button of screen.getAllByRole("button")) {
      expect(button).toBeDisabled();
    }
  });

  it("sends only once even when clicked twice quickly", async () => {
    const onChoose = vi.fn().mockReturnValue(true);
    render(<ExploreAspectChoices overview={OVERVIEW} onChoose={onChoose} />);

    const button = screen.getByRole("button", { name: "最初から" });
    await userEvent.click(button);
    await userEvent.click(button);

    expect(onChoose).toHaveBeenCalledTimes(1);
  });

  it("lets the learner try again when the message could not be sent", async () => {
    const onChoose = vi.fn().mockReturnValue(false);
    render(<ExploreAspectChoices overview={OVERVIEW} onChoose={onChoose} />);

    const button = screen.getByRole("button", { name: "最初から" });
    await userEvent.click(button);
    await userEvent.click(button);

    expect(onChoose).toHaveBeenCalledTimes(2);
  });
});
