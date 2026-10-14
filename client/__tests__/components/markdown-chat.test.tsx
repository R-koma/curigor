import { beforeEach, describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import mermaid from "mermaid";
import { Markdown } from "@/components/ui/markdown";
import { closeOpenBlocks } from "@/lib/chat-markdown";

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async () => ({
      svg: '<svg data-testid="diagram"></svg>',
      diagramType: "flowchart",
    })),
  },
}));

const codeMessage = ["```python", 'print("hello")', "```"].join("\n");
const VARIANTS = ["default", "chat", "article", "inline"] as const;

describe("Markdown (chat variant)", () => {
  it("renders fenced code as a highlighted code block", () => {
    const { container } = render(
      <Markdown variant="chat">{codeMessage}</Markdown>,
    );

    const code = container.querySelector("pre code");
    expect(code).not.toBeNull();
    expect(code?.className).toContain("language-python");
    expect(container.querySelector("pre")?.textContent).toContain(
      'print("hello")',
    );
  });

  it("renders prose without introducing any button", () => {
    render(<Markdown variant="chat">{"ただのテキストです"}</Markdown>);

    expect(screen.getByText("ただのテキストです")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("Markdown math", () => {
  it.each(VARIANTS)("renders inline math with KaTeX in %s", (variant) => {
    const { container } = render(
      <Markdown variant={variant}>{"面積は $\\pi r^2$ です"}</Markdown>,
    );

    expect(container.querySelector(".katex")).not.toBeNull();
  });

  it("renders \\[ \\] as display math", () => {
    const { container } = render(
      <Markdown variant="chat">{"次の式です\n\\[x^2\\]"}</Markdown>,
    );

    expect(container.querySelector(".katex-display")).not.toBeNull();
  });

  it("renders a one-line $$ formula as display math", () => {
    const { container } = render(
      <Markdown variant="article">{"$$E = mc^2$$"}</Markdown>,
    );

    expect(container.querySelector(".katex-display")).not.toBeNull();
  });

  it("keeps the source of a broken formula without throwing", () => {
    const { container } = render(
      <Markdown variant="chat">{"$\\frac{1}{$"}</Markdown>,
    );

    expect(container.textContent).toContain("\\frac{1}{");
  });

  it("does not read underscores and asterisks in math as emphasis", () => {
    const { container } = render(
      <Markdown variant="chat">{"$a_1 * b_2 * c$"}</Markdown>,
    );

    expect(container.querySelector("em")).toBeNull();
    expect(container.querySelector(".katex")).not.toBeNull();
  });

  it("leaves dollar signs inside inline code alone", () => {
    const { container } = render(
      <Markdown variant="chat">{"`echo $HOME $PATH`"}</Markdown>,
    );

    expect(container.querySelector(".katex")).toBeNull();
    expect(container.querySelector("code")?.textContent).toBe(
      "echo $HOME $PATH",
    );
  });

  it("renders paragraphs without vertical margins in the inline variant", () => {
    const { container } = render(
      <Markdown variant="inline" className="text-sm">
        {"一行です"}
      </Markdown>,
    );

    expect(container.querySelector("p")?.className).toContain("my-0");
    expect(container.firstElementChild?.className).toBe("text-sm");
  });
});

describe("Markdown diagrams", () => {
  const diagram = ["```mermaid", "graph TD", "  A --> B", "```"].join("\n");

  beforeEach(() => {
    vi.mocked(mermaid.render).mockClear();
  });

  it.each(["default", "chat", "article"] as const)(
    "draws a mermaid block as a diagram in %s",
    async (variant) => {
      render(<Markdown variant={variant}>{diagram}</Markdown>);

      expect(await screen.findByTestId("diagram")).toBeInTheDocument();
      expect(mermaid.render).toHaveBeenCalledWith(
        expect.any(String),
        "graph TD\n  A --> B",
      );
    },
  );

  it("shows a progress line for a diagram still being streamed", () => {
    render(
      <Markdown variant="chat">
        {closeOpenBlocks("図です\n```mermaid\ngraph TD")}
      </Markdown>,
    );

    expect(screen.getByText("図を描いています…")).toBeInTheDocument();
    expect(mermaid.render).not.toHaveBeenCalled();
  });
});
