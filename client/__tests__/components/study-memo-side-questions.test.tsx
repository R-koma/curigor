import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StudyMemoAspect } from "@/components/study-memos/study-memo-aspect";
import type { StudyMemoGroup } from "@/lib/study-memos";

function group(questions: StudyMemoGroup["questions"]): StudyMemoGroup {
  return { key: "a", name: "観点", isCore: true, questions, terms: [] };
}

describe("StudyMemoAspect with side questions", () => {
  it("question with quote renders the quote line", () => {
    render(
      <StudyMemoAspect
        defaultOpen
        group={group([
          {
            question: "なぜ速い",
            answer: "",
            quote: "索引を使うと速い",
            childDepth: 0,
          },
        ])}
      />,
    );

    const quote = screen.getByText("索引を使うと速い");
    const question = screen.getByText("なぜ速い");
    expect(
      quote.compareDocumentPosition(question) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("child question is rendered under its parent with indent", () => {
    render(
      <StudyMemoAspect
        defaultOpen
        group={group([
          { question: "親の疑問", answer: "", quote: "B木", childDepth: 0 },
          { question: "子の疑問", answer: "", quote: "枝", childDepth: 1 },
        ])}
      />,
    );

    const child = screen.getByText("子の疑問").closest("li");
    const parent = screen.getByText("親の疑問").closest("li");
    expect(child).toHaveAttribute("data-child-depth", "1");
    expect(parent).not.toHaveAttribute("data-child-depth");
  });

  it("old memo without new fields renders as before", () => {
    render(
      <StudyMemoAspect
        defaultOpen
        group={group([
          { question: "普通の疑問", answer: "答え", childDepth: 0 },
        ])}
      />,
    );

    const item = screen.getByText("普通の疑問").closest("li");
    expect(item).not.toHaveAttribute("data-child-depth");
    expect(item?.querySelector("[data-quote]")).toBeNull();
  });
});
