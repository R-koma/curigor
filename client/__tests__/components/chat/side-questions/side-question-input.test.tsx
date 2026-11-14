import { beforeEach, describe, expect, it, vi } from "vitest";
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

describe("SideQuestionInput の書きかけ", () => {
  const KEY = "curigor:draft:side:t1";

  beforeEach(() => {
    sessionStorage.clear();
  });

  function renderKeyed(initialValue?: string, draftKey: string | null = KEY) {
    const onSend = vi.fn();
    render(
      <SideQuestionInput
        hasMessages
        disabled={false}
        onSend={onSend}
        draftKey={draftKey ?? undefined}
        initialValue={initialValue}
      />,
    );
    return screen.getByRole("textbox") as HTMLInputElement;
  }

  it("保存した書きかけが入る", () => {
    sessionStorage.setItem(KEY, "続きの問い");
    expect(renderKeyed().value).toBe("続きの問い");
  });

  it("入力すると保存し、送信すると消える", () => {
    const input = renderKeyed();
    fireEvent.change(input, { target: { value: "続きの問い" } });
    expect(sessionStorage.getItem(KEY)).toBe("続きの問い");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });

  it("draftKey が無ければ保存しない", () => {
    const input = renderKeyed(undefined, null);
    fireEvent.change(input, { target: { value: "続きの問い" } });
    expect(sessionStorage.length).toBe(0);
  });

  it("initialValue（送信の失敗）が保存より優先される", () => {
    sessionStorage.setItem(KEY, "a");
    expect(renderKeyed("b").value).toBe("b");
  });
});

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
