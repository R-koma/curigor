import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { SideQuestionInput } from "@/components/chat/side-questions/side-question-input";

function renderInput(initialValue?: string) {
  const props = { hasMessages: true, disabled: false, onSend: vi.fn() };
  const view = render(
    <SideQuestionInput {...props} initialValue={initialValue} />,
  );
  return {
    input: screen.getByRole("textbox") as HTMLInputElement,
    update: (next?: string) =>
      view.rerender(<SideQuestionInput {...props} initialValue={next} />),
  };
}

describe("SideQuestionInput", () => {
  it("clears the restored text once the retry has gone through", () => {
    const { input, update } = renderInput("索引とは？");
    expect(input.value).toBe("索引とは？");

    update(undefined);

    expect(input.value).toBe("");
  });

  it("keeps text the user typed over the restored one", () => {
    const { input, update } = renderInput("索引とは？");
    fireEvent.change(input, { target: { value: "B木とは？" } });

    update(undefined);

    expect(input.value).toBe("B木とは？");
  });

  it("restores the text again when the retry fails too", () => {
    const { input, update } = renderInput("索引とは？");
    update(undefined);

    update("索引とは？");

    expect(input.value).toBe("索引とは？");
  });
});
