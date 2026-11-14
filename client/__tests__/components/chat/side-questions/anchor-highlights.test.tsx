import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { AnchorHighlights } from "@/components/chat/side-questions/anchor-highlights";

class FakeHighlight {
  ranges: Range[];
  constructor(...ranges: Range[]) {
    this.ranges = ranges;
  }
}

const rect = new DOMRect(0, 0, 100, 20);
const originalRects = Range.prototype.getClientRects;

beforeEach(() => {
  vi.stubGlobal("Highlight", FakeHighlight);
  vi.stubGlobal("CSS", { ...globalThis.CSS, highlights: new Map() });
  Range.prototype.getClientRects = () =>
    [rect] as unknown as ReturnType<Range["getClientRects"]>;
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  Range.prototype.getClientRects = originalRects;
});

async function setup() {
  const onOpen = vi.fn();
  render(
    <div>
      <div data-message-id="m1">
        <p>索引を使うと速く探せる</p>
      </div>
      <textarea aria-label="入力欄" />
      <button type="button">ここについて質問</button>
      <AnchorHighlights
        anchors={[
          {
            id: "q1",
            rootSelector: '[data-message-id="m1"]',
            quote: "索引",
            occurrence: 0,
          },
        ]}
        hoverId={null}
        openIds={new Set()}
        onOpen={onOpen}
      />
    </div>,
  );
  await act(async () => {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  });
  return onOpen;
}

describe("AnchorHighlights", () => {
  it("opens the thread when the underlined passage itself is clicked", async () => {
    const onOpen = await setup();

    fireEvent.click(screen.getByText("索引を使うと速く探せる"), {
      clientX: 10,
      clientY: 10,
    });

    expect(onOpen).toHaveBeenCalledWith("q1");
  });

  it("ignores clicks on other elements that sit over the same coordinates", async () => {
    const onOpen = await setup();

    fireEvent.click(screen.getByLabelText("入力欄"), {
      clientX: 10,
      clientY: 10,
    });
    fireEvent.click(screen.getByRole("button", { name: "ここについて質問" }), {
      clientX: 10,
      clientY: 10,
    });

    expect(onOpen).not.toHaveBeenCalled();
  });
});
