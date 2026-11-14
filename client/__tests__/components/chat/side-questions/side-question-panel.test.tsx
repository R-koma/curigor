import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SideQuestionPanel } from "@/components/chat/side-questions/side-question-panel";
import type { SideThreadView } from "@/components/chat/side-questions/side-question-card";
import type { SideQuestion } from "@/lib/side-questions";

const parent: SideQuestion = {
  id: "p",
  parentId: null,
  anchorMessageId: "m1",
  anchorSideMessageId: null,
  quote: "B木",
  occurrence: 0,
  depth: 0,
  messages: [
    { id: "pu1", role: "user", content: "B木とは？" },
    { id: "pa1", role: "assistant", content: "枝の多い木です。" },
    { id: "pu2", role: "user", content: "なぜ速い？" },
    { id: "pa2", role: "assistant", content: "高さが低いからです。" },
  ],
};
const child: SideQuestion = {
  id: "c",
  parentId: "p",
  anchorMessageId: null,
  anchorSideMessageId: "pa1",
  quote: "枝",
  occurrence: 0,
  depth: 1,
  messages: [
    { id: "cu1", role: "user", content: "枝とは？" },
    { id: "ca1", role: "assistant", content: "分かれ道です。" },
  ],
};

function view(overrides: Partial<SideThreadView> = {}): SideThreadView {
  return {
    threads: [parent, child],
    open: new Set(),
    streaming: null,
    error: null,
    focusId: null,
    onToggle: vi.fn(),
    onSend: vi.fn(),
    onHover: vi.fn(),
    ...overrides,
  };
}

function renderPanel(v: SideThreadView, onFoldAll = vi.fn()) {
  render(
    <SideQuestionPanel
      view={v}
      messageOrder={["m1"]}
      overlayClosed={false}
      onFoldAll={onFoldAll}
      onCloseOverlay={vi.fn()}
    />,
  );
  return onFoldAll;
}

describe("SideQuestionPanel", () => {
  it("shows the heading with the count", () => {
    renderPanel(view());

    const heading = screen.getByRole("heading", { name: /質問/ });
    expect(heading).toHaveTextContent("2");
  });

  it("collapsed card shows first question and quote, and child rows", async () => {
    const v = view();
    renderPanel(v);

    expect(screen.getByText("B木とは？")).toBeInTheDocument();
    expect(screen.getByText("B木")).toBeInTheDocument();
    expect(screen.getByText("枝とは？")).toBeInTheDocument();
    expect(screen.queryByText("枝の多い木です。")).not.toBeInTheDocument();

    await userEvent.click(screen.getByText("枝とは？"));
    expect(v.onToggle).toHaveBeenCalledWith("c");
  });

  it("open card shows quote, messages and input; child sits right after its answer", () => {
    renderPanel(view({ open: new Set(["p"]) }));

    expect(screen.getByText("B木")).toBeInTheDocument();
    expect(screen.getByText("枝の多い木です。")).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: "続けて聞く" }),
    ).toBeInTheDocument();
    const firstAnswer = screen.getByText("枝の多い木です。");
    const childRow = screen.getByText("枝とは？");
    const secondQuestion = screen.getByText("なぜ速い？");
    expect(
      firstAnswer.compareDocumentPosition(childRow) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      childRow.compareDocumentPosition(secondQuestion) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("answers carry the side message id for selection", () => {
    renderPanel(view({ open: new Set(["p"]) }));

    const answer = screen
      .getByText("枝の多い木です。")
      .closest("[data-side-message-id]");
    expect(answer).toHaveAttribute("data-side-message-id", "pa1");
    expect(answer).toHaveAttribute("data-side-thread-id", "p");
    expect(answer).toHaveAttribute("data-side-selectable");
  });

  it("answers at the deepest level cannot be selected", () => {
    const deep = { ...child, depth: 3 };
    renderPanel(view({ threads: [parent, deep], open: new Set(["p", "c"]) }));

    const answer = screen
      .getByText("分かれ道です。")
      .closest("[data-side-message-id]");
    expect(answer).not.toHaveAttribute("data-side-selectable");
  });

  it("opening a child keeps the parent open", () => {
    renderPanel(view({ open: new Set(["p", "c"]) }));

    expect(screen.getByText("枝の多い木です。")).toBeInTheDocument();
    expect(screen.getByText("分かれ道です。")).toBeInTheDocument();
    expect(screen.getAllByRole("textbox")).toHaveLength(2);
  });

  it('fold-all button is disabled when nothing is open and has aria-label "すべて畳む"', async () => {
    renderPanel(view());
    expect(screen.getByRole("button", { name: "すべて畳む" })).toBeDisabled();
  });

  it("fold-all folds when something is open", async () => {
    const onFoldAll = renderPanel(view({ open: new Set(["p"]) }));

    await userEvent.click(screen.getByRole("button", { name: "すべて畳む" }));

    expect(onFoldAll).toHaveBeenCalled();
  });

  it("Enter during IME composition does not send", () => {
    const v = view({ open: new Set(["p"]) });
    renderPanel(v);
    const input = screen.getByRole("textbox", { name: "続けて聞く" });

    fireEvent.change(input, { target: { value: "もっと" } });
    fireEvent.keyDown(input, { key: "Enter", isComposing: true });
    expect(v.onSend).not.toHaveBeenCalled();

    fireEvent.keyDown(input, { key: "Enter" });
    expect(v.onSend).toHaveBeenCalledWith("p", "もっと");
  });

  it("send button is disabled while empty", () => {
    renderPanel(view({ open: new Set(["p"]) }));

    expect(screen.getByRole("button", { name: "送信" })).toBeDisabled();
  });

  it("inputs are disabled while streaming", () => {
    renderPanel(
      view({
        open: new Set(["p", "c"]),
        streaming: { sideQuestionId: "c", question: "", text: "考え中" },
      }),
    );

    for (const input of screen.getAllByRole("textbox")) {
      expect(input).toBeDisabled();
    }
    expect(screen.getByText("考え中")).toBeInTheDocument();
  });

  it("a draft shows the first-question placeholder", () => {
    const draft: SideQuestion = {
      ...parent,
      id: "d",
      quote: "索引",
      messages: [],
    };
    renderPanel(view({ threads: [draft], open: new Set(["d"]), focusId: "d" }));

    const input = screen.getByRole("textbox", {
      name: "ここについて聞きたいこと",
    });
    expect(input).toHaveFocus();
    expect(screen.getByText("索引")).toBeInTheDocument();
  });

  it("error shows detail and retry sends the same content", async () => {
    const v = view({
      open: new Set(["p"]),
      error: { id: "p", detail: "回答を作れませんでした", content: "もう一度" },
    });
    renderPanel(v);

    const alert = screen.getByRole("alert");
    expect(
      within(alert).getByText("回答を作れませんでした"),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "続けて聞く" })).toHaveValue(
      "もう一度",
    );
    await userEvent.click(screen.getByRole("button", { name: "もう一度送る" }));

    expect(v.onSend).toHaveBeenCalledWith("p", "もう一度");
  });

  it('no text "往復" anywhere', () => {
    const { container } = render(
      <SideQuestionPanel
        view={view({ open: new Set(["p", "c"]) })}
        messageOrder={["m1"]}
        overlayClosed={false}
        onFoldAll={vi.fn()}
        onCloseOverlay={vi.fn()}
      />,
    );

    expect(container.textContent).not.toContain("往復");
  });
});
