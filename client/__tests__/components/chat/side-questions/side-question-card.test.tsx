import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  SideQuestionCard,
  type SideThreadView,
} from "@/components/chat/side-questions/side-question-card";
import type { SideQuestion } from "@/lib/side-questions";

const unanchored: SideQuestion = {
  id: "q",
  parentId: null,
  anchorMessageId: "m1",
  anchorSideMessageId: null,
  quote: "",
  occurrence: 0,
  depth: 0,
  messages: [
    {
      id: "u",
      role: "user",
      content: "あ".repeat(45),
    },
    { id: "a", role: "assistant", content: "答え" },
  ],
};

function view(open: boolean): SideThreadView {
  return {
    threads: [unanchored],
    open: new Set(open ? ["q"] : []),
    streaming: null,
    error: null,
    focusId: null,
    onToggle: vi.fn(),
    onSend: vi.fn(),
    onHover: vi.fn(),
  };
}

describe("SideQuestionCard without a quote", () => {
  it("folded: shows the first question and no quote line", () => {
    const { container } = render(
      <SideQuestionCard thread={unanchored} view={view(false)} />,
    );

    const button = screen.getByRole("button");
    expect(button.querySelectorAll("span")).toHaveLength(1);
    expect(container.textContent).not.toContain("「」");
  });

  it("open: heads the card with the first 40 characters of the first question", () => {
    render(<SideQuestionCard thread={unanchored} view={view(true)} />);

    expect(
      screen.getByText(`${"あ".repeat(40)}…`, { selector: "p" }),
    ).toBeInTheDocument();
  });

  it("open draft without messages shows a placeholder heading", () => {
    const draft = { ...unanchored, id: "d", messages: [] };
    render(
      <SideQuestionCard
        thread={draft}
        view={{ ...view(true), threads: [draft], open: new Set(["d"]) }}
      />,
    );

    expect(screen.getByText("新しい質問")).toBeInTheDocument();
  });
});
