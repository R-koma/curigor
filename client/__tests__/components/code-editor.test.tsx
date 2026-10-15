import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CodeEditor } from "@/components/chat/code-editor";
import { loadCodeMirror } from "@/lib/codemirror";

vi.mock("@/lib/codemirror", () => ({ loadCodeMirror: vi.fn() }));

describe("CodeEditor", () => {
  it("offers a retry when the editor cannot be loaded", async () => {
    vi.mocked(loadCodeMirror).mockRejectedValue(new Error("offline"));
    render(<CodeEditor fence="" onChange={vi.fn()} onSubmit={vi.fn()} />);

    expect(
      await screen.findByText("エディタを読み込めませんでした"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "再試行" }));

    expect(loadCodeMirror).toHaveBeenCalledTimes(2);
  });
});
