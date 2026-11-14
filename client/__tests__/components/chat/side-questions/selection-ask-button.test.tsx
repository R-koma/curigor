import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { SelectionAskButton } from "@/components/chat/side-questions/selection-ask-button";

Range.prototype.getBoundingClientRect ??= () => new DOMRect(10, 20, 30, 10);

function setup() {
  const onAsk = vi.fn();
  render(
    <div>
      <div data-message-id="m1" data-side-selectable="">
        <p>索引を使うと速く探せる</p>
      </div>
      <div>
        <p>ユーザーの発言です</p>
      </div>
    </div>,
  );
  render(<SelectionAskButton onAsk={onAsk} />);
  return onAsk;
}

async function select(text: string, word: string) {
  const node = screen.getByText(text).firstChild as Text;
  const at = node.data.indexOf(word);
  const range = document.createRange();
  range.setStart(node, at);
  range.setEnd(node, at + word.length);
  const selection = window.getSelection()!;
  selection.removeAllRanges();
  selection.addRange(range);
  await act(async () => {
    fireEvent.mouseUp(document);
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("SelectionAskButton", () => {
  it("ask button appears for a valid selection in an assistant message and not in a user message", async () => {
    const onAsk = setup();

    await select("ユーザーの発言です", "発言");
    expect(
      screen.queryByRole("button", { name: "ここについて質問" }),
    ).not.toBeInTheDocument();

    await select("索引を使うと速く探せる", "索引");
    const button = screen.getByRole("button", { name: "ここについて質問" });
    fireEvent.click(button);

    expect(onAsk).toHaveBeenCalledWith(
      expect.objectContaining({ quote: "索引", occurrence: 0 }),
    );
    expect(onAsk.mock.calls[0][0].root.dataset.messageId).toBe("m1");
  });

  it("hides on Escape", async () => {
    setup();
    await select("索引を使うと速く探せる", "索引");

    fireEvent.keyDown(document, { key: "Escape" });

    expect(
      screen.queryByRole("button", { name: "ここについて質問" }),
    ).not.toBeInTheDocument();
  });
});
