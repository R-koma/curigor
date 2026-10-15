import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InsertPanel } from "@/components/chat/insert-panel";

vi.mock("@/components/chat/math-editor", () => ({
  MathEditor: ({
    initialValue,
    onChange,
    onSubmit,
  }: {
    initialValue: string;
    onChange: (value: string) => void;
    onSubmit: () => void;
  }) => (
    <input
      aria-label="数式"
      defaultValue={initialValue}
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={(event) => event.key === "Enter" && onSubmit()}
    />
  ),
}));

vi.mock("@/components/chat/code-editor", () => ({
  CodeEditor: ({
    fence,
    onChange,
  }: {
    fence: string;
    onChange: (value: string) => void;
  }) => (
    <textarea
      aria-label="コード"
      className="cm-editor"
      data-fence={fence}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

function renderPanel(props: Partial<Parameters<typeof InsertPanel>[0]> = {}) {
  const handlers = {
    onInsertMath: vi.fn(),
    onInsertCode: vi.fn(),
    onClose: vi.fn(),
    onKeyboardHeight: vi.fn(),
  };
  render(<InsertPanel kind="math" {...handlers} {...props} />);
  return handlers;
}

afterEach(() => localStorage.clear());

describe("InsertPanel", () => {
  it("cannot insert while empty", () => {
    renderPanel();

    expect(screen.getByRole("button", { name: "挿入" })).toBeDisabled();
  });

  it("inserts the trimmed formula", async () => {
    const { onInsertMath } = renderPanel();

    await userEvent.type(screen.getByLabelText("数式"), " x^2 ");
    await userEvent.click(screen.getByRole("button", { name: "挿入" }));

    expect(onInsertMath).toHaveBeenCalledWith("x^2");
  });

  it("inserts from the editor's submit key", async () => {
    const { onInsertMath } = renderPanel();

    await userEvent.type(screen.getByLabelText("数式"), "x{Enter}");

    expect(onInsertMath).toHaveBeenCalledWith("x");
  });

  it("starts from the formula being edited", () => {
    renderPanel({ initialLatex: "\\pi" });

    expect(screen.getByLabelText("数式")).toHaveValue("\\pi");
    expect(screen.getByRole("button", { name: "挿入" })).toBeEnabled();
  });

  it("closes with Escape", async () => {
    const { onClose } = renderPanel();

    await userEvent.type(screen.getByLabelText("数式"), "{Escape}");

    expect(onClose).toHaveBeenCalled();
  });

  it("leaves Escape inside the code editor to the editor", async () => {
    const { onClose } = renderPanel({ kind: "code" });

    await userEvent.type(screen.getByLabelText("コード"), "{Escape}");

    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes with the close button", async () => {
    const { onClose } = renderPanel();

    await userEvent.click(screen.getByRole("button", { name: "閉じる" }));

    expect(onClose).toHaveBeenCalled();
  });

  it("inserts code with the chosen language and remembers it", async () => {
    const { onInsertCode } = renderPanel({ kind: "code" });

    await userEvent.selectOptions(screen.getByLabelText("言語"), "python");
    await userEvent.type(screen.getByLabelText("コード"), "print(1)");
    await userEvent.click(screen.getByRole("button", { name: "挿入" }));

    expect(onInsertCode).toHaveBeenCalledWith("print(1)", "python");
    expect(screen.getByLabelText("コード")).toHaveAttribute(
      "data-fence",
      "python",
    );
    expect(localStorage.getItem("code-language")).toBe("python");
  });

  it("starts from the language chosen last time", () => {
    localStorage.setItem("code-language", "go");
    renderPanel({ kind: "code" });

    expect(screen.getByLabelText("言語")).toHaveValue("go");
  });
});
