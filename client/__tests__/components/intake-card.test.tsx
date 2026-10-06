import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IntakeCardView } from "@/components/chat/intake-card";
import { ALL_SKIPPED_TEXT, type IntakeCard } from "@/lib/intake";

const card: IntakeCard = {
  questions: [
    {
      key: "purpose",
      header: "目的",
      question: "今回、何ができるようになりたいですか？",
      options: [
        { label: "仕事で使う", description: "" },
        { label: "面接対策", description: "" },
      ],
      multi_select: false,
      preselected: [],
    },
    {
      key: "source",
      header: "教材",
      question: "何を使って学びますか？",
      options: [
        { label: "書籍", description: "" },
        { label: "動画", description: "" },
      ],
      multi_select: true,
      preselected: [],
    },
    {
      key: "prior_knowledge",
      header: "今の理解",
      question: "今どのくらい知っていますか？",
      options: [{ label: "初めて学ぶ", description: "" }],
      multi_select: false,
      preselected: [],
    },
  ],
};

describe("IntakeCardView", () => {
  it("walks through questions and submits formatted answers", async () => {
    const onSubmit = vi.fn();
    render(<IntakeCardView card={card} onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole("radio", { name: /仕事で使う/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /書籍/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /動画/ }));
    await userEvent.click(screen.getByRole("button", { name: "次へ" }));
    await userEvent.click(screen.getByRole("button", { name: "スキップ" }));
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSubmit).toHaveBeenCalledWith(
      "目的: 仕事で使う\n教材: 書籍、動画",
      {
        topic: "",
        purpose: "仕事で使う",
        source: ["書籍", "動画"],
        prior_knowledge: "",
      },
    );
  });

  it("accepts free text via the other option", async () => {
    const onSubmit = vi.fn();
    render(<IntakeCardView card={card} onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole("radio", { name: /その他/ }));
    await userEvent.type(
      screen.getByRole("textbox"),
      "社内勉強会で話す{Enter}",
    );
    await userEvent.click(screen.getByRole("tab", { name: /確認/ }));
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSubmit.mock.calls[0][1].purpose).toBe("社内勉強会で話す");
  });

  it("selects options with number keys", async () => {
    render(<IntakeCardView card={card} onSubmit={vi.fn()} />);

    screen.getByRole("radiogroup").focus();
    await userEvent.keyboard("2");

    expect(screen.getByRole("tab", { name: /目的/ })).toHaveAttribute(
      "data-answered",
      "true",
    );
    expect(screen.getByRole("group")).toBeInTheDocument();
  });

  it("can skip everything at once", async () => {
    const onSubmit = vi.fn();
    render(<IntakeCardView card={card} onSubmit={onSubmit} />);

    await userEvent.click(
      screen.getByRole("button", { name: "すべてスキップして始める" }),
    );

    expect(onSubmit).toHaveBeenCalledWith(ALL_SKIPPED_TEXT, {
      topic: "",
      purpose: "",
      source: [],
      prior_knowledge: "",
    });
  });

  it("ignores interaction while disabled", async () => {
    const onSubmit = vi.fn();
    render(<IntakeCardView card={card} onSubmit={onSubmit} disabled />);

    await userEvent.click(
      screen.getByRole("button", { name: "すべてスキップして始める" }),
    );

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits only once when 送信 is clicked repeatedly", async () => {
    const onSubmit = vi.fn();
    render(<IntakeCardView card={card} onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole("tab", { name: /確認/ }));
    await userEvent.dblClick(screen.getByRole("button", { name: "送信" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("submits only once when skip-all is clicked repeatedly", async () => {
    const onSubmit = vi.fn();
    render(<IntakeCardView card={card} onSubmit={onSubmit} />);

    await userEvent.dblClick(
      screen.getByRole("button", { name: "すべてスキップして始める" }),
    );

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});

const topicQuestion = (
  options: { label: string; description: string }[],
): IntakeCard["questions"][number] => ({
  key: "topic",
  header: "トピック",
  question: "何について学びますか？",
  options,
  multi_select: false,
  preselected: [],
});

describe("IntakeCardView topic question", () => {
  it("shows the input right away when there are no candidates", async () => {
    const onSubmit = vi.fn();
    render(
      <IntakeCardView
        card={{ questions: [topicQuestion([]), ...card.questions] }}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByText("何について学びますか？")).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    const input = screen.getByRole("textbox", { name: "トピック" });
    expect(input).toHaveAttribute("maxlength", "60");

    await userEvent.type(input, "Linuxの仕組み{Enter}");
    expect(
      screen.getByText("今回、何ができるようになりたいですか？"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /確認/ }));
    expect(screen.getByText("トピック: Linuxの仕組み")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSubmit.mock.calls[0][1].topic).toBe("Linuxの仕組み");
  });

  it("offers candidates plus free input when there are candidates", async () => {
    const onSubmit = vi.fn();
    render(
      <IntakeCardView
        card={{
          questions: [
            topicQuestion([{ label: "Linuxの仕組み", description: "" }]),
          ],
        }}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: /その他/ }));
    expect(screen.getByRole("textbox", { name: "トピック" })).toHaveAttribute(
      "maxlength",
      "60",
    );
  });

  it("selects a candidate and moves on", async () => {
    const onSubmit = vi.fn();
    render(
      <IntakeCardView
        card={{
          questions: [
            topicQuestion([{ label: "Linuxの仕組み", description: "" }]),
          ],
        }}
        onSubmit={onSubmit}
      />,
    );

    await userEvent.click(screen.getByRole("radio", { name: /Linuxの仕組み/ }));
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSubmit.mock.calls[0][1].topic).toBe("Linuxの仕組み");
  });

  it("reaches the skip button by Tab and ignores number keys without candidates", async () => {
    render(
      <IntakeCardView
        card={{ questions: [topicQuestion([]), ...card.questions] }}
        onSubmit={vi.fn()}
      />,
    );

    await userEvent.keyboard("1");
    expect(screen.getByRole("textbox", { name: "トピック" })).toHaveValue("");
    expect(screen.getByRole("tab", { name: /トピック/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    screen.getByRole("textbox", { name: "トピック" }).focus();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "スキップ" })).toHaveFocus();
  });

  it("keeps the skipped topic empty in the answers", async () => {
    const onSubmit = vi.fn();
    render(
      <IntakeCardView
        card={{ questions: [topicQuestion([]), ...card.questions] }}
        onSubmit={onSubmit}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "スキップ" }));
    await userEvent.click(screen.getByRole("tab", { name: /確認/ }));
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSubmit.mock.calls[0][1].topic).toBe("");
  });

  it("labels the free input of every question", async () => {
    render(<IntakeCardView card={card} onSubmit={vi.fn()} />);

    await userEvent.click(screen.getByRole("radio", { name: /その他/ }));

    expect(screen.getByRole("textbox", { name: "目的" })).toBeInTheDocument();
  });
});
