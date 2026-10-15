import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MathEditor } from "@/components/chat/math-editor";
import { loadMathLive, watchKeyboardHeight } from "@/lib/mathlive";

vi.mock("@/lib/mathlive", () => ({
  loadMathLive: vi.fn(),
  watchKeyboardHeight: vi.fn(() => () => {}),
}));

class FakeMathfield extends HTMLElement {
  value = "";
  mathVirtualKeyboardPolicy = "";
}
customElements.define("fake-math-field", FakeMathfield);

const mathlive = { MathfieldElement: FakeMathfield } as unknown as Awaited<
  ReturnType<typeof loadMathLive>
>;

function renderEditor(props: Partial<Parameters<typeof MathEditor>[0]> = {}) {
  const handlers = {
    onChange: vi.fn(),
    onSubmit: vi.fn(),
    onKeyboardHeight: vi.fn(),
  };
  const view = render(<MathEditor initialValue="x" {...handlers} {...props} />);
  return { ...view, ...handlers };
}

async function field(container: HTMLElement) {
  return waitFor(() => {
    const element = container.querySelector("fake-math-field");
    if (!element) throw new Error("not mounted");
    return element as FakeMathfield;
  });
}

beforeEach(() => {
  vi.mocked(loadMathLive).mockReset().mockResolvedValue(mathlive);
});

describe("MathEditor", () => {
  it("starts from the initial formula", async () => {
    const { container } = renderEditor();

    expect((await field(container)).value).toBe("x");
  });

  it("reports what is typed", async () => {
    const { container, onChange } = renderEditor();
    const element = await field(container);

    element.value = "x^2";
    element.dispatchEvent(new Event("input"));

    expect(onChange).toHaveBeenCalledWith("x^2");
  });

  it("submits on Enter instead of breaking the line", async () => {
    const { container, onSubmit } = renderEditor();
    const event = new InputEvent("beforeinput", {
      inputType: "insertLineBreak",
      cancelable: true,
    });

    (await field(container)).dispatchEvent(event);

    expect(onSubmit).toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(true);
  });

  it("passes on the virtual keyboard height", async () => {
    vi.mocked(watchKeyboardHeight).mockImplementationOnce((onHeight) => {
      onHeight(300);
      return () => {};
    });
    const { container, onKeyboardHeight } = renderEditor();

    await field(container);

    expect(onKeyboardHeight).toHaveBeenCalledWith(300);
  });

  it("offers a retry when the editor cannot be loaded", async () => {
    vi.mocked(loadMathLive).mockRejectedValueOnce(new Error("offline"));
    const { container } = renderEditor();

    expect(
      await screen.findByText("エディタを読み込めませんでした"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "再試行" }));

    expect(await field(container)).toBeInstanceOf(FakeMathfield);
    expect(loadMathLive).toHaveBeenCalledTimes(2);
  });
});
