import { describe, it, expect } from "vitest";
import {
  closeOpenBlocks,
  closeOpenCodeFence,
  closeOpenMathBlock,
  mapOutsideCode,
  normalizeMathDelimiters,
} from "@/lib/chat-markdown";

describe("closeOpenCodeFence", () => {
  it("appends a closing fence when a code block is left open", () => {
    const streaming = "説明します\n```python\nprint('hi')";
    expect(closeOpenCodeFence(streaming)).toBe(
      "説明します\n```python\nprint('hi')\n```",
    );
  });

  it("leaves content untouched when fences are balanced", () => {
    const closed = "```python\nprint('hi')\n```";
    expect(closeOpenCodeFence(closed)).toBe(closed);
  });

  it("leaves plain text without fences untouched", () => {
    const text = "コードはまだありません";
    expect(closeOpenCodeFence(text)).toBe(text);
  });

  it("only counts fences at the start of a line", () => {
    const inline = "これは ```inline``` ではない";
    expect(closeOpenCodeFence(inline)).toBe(inline);
  });

  it("marks a mermaid block still being streamed as pending", () => {
    expect(
      closeOpenCodeFence("図です\n```mermaid\ngraph TD", { streaming: true }),
    ).toBe("図です\n```mermaid-pending\ngraph TD\n```");
  });

  it("keeps an unclosed mermaid block of a finished message as a diagram", () => {
    expect(closeOpenCodeFence("図です\n```mermaid\ngraph TD")).toBe(
      "図です\n```mermaid\ngraph TD\n```",
    );
  });

  it("leaves a closed mermaid block alone", () => {
    const closed = "```mermaid\ngraph TD\n```";
    expect(closeOpenCodeFence(closed)).toBe(closed);
  });

  it("only marks the block that is open", () => {
    const streaming = "```mermaid\ngraph TD\n```\n```python\nx = 1";
    expect(closeOpenCodeFence(streaming)).toBe(`${streaming}\n\`\`\``);
  });
});

describe("mapOutsideCode", () => {
  it("transforms prose and keeps fenced and inline code as is", () => {
    const markdown = "a `a` a\n```\na\n```\na";
    expect(mapOutsideCode(markdown, (text) => text.replaceAll("a", "b"))).toBe(
      "b `a` b\n```\na\n```\nb",
    );
  });

  it("treats an unclosed fence as code", () => {
    expect(mapOutsideCode("a\n```\na", (text) => text.toUpperCase())).toBe(
      "A\n```\na",
    );
  });
});

describe("normalizeMathDelimiters", () => {
  it("turns \\( \\) into inline dollars", () => {
    expect(normalizeMathDelimiters("式 \\(x^2\\) です")).toBe("式 $x^2$ です");
  });

  it("turns \\[ \\] into a display block on its own lines", () => {
    expect(normalizeMathDelimiters("\\[x^2\\]")).toBe("\n$$\nx^2\n$$\n");
  });

  it("splits a one-line $$ formula into a display block", () => {
    expect(normalizeMathDelimiters("$$E = mc^2$$")).toBe("$$\nE = mc^2\n$$");
  });

  it("keeps $$ inside a sentence inline", () => {
    const text = "式 $$x$$ です";
    expect(normalizeMathDelimiters(text)).toBe(text);
  });

  it("does not touch delimiters inside code", () => {
    const markdown = "`\\(x\\)`\n```\n\\[y\\]\n$$z$$\n```";
    expect(normalizeMathDelimiters(markdown)).toBe(markdown);
  });

  it("gives the same result when applied twice", () => {
    const markdown = "\\(a\\) と \\[b\\] と\n$$c$$";
    const once = normalizeMathDelimiters(markdown);
    expect(normalizeMathDelimiters(once)).toBe(once);
  });
});

describe("closeOpenMathBlock", () => {
  it("closes a display block left open", () => {
    expect(closeOpenMathBlock("答え\n$$\nx^2")).toBe("答え\n$$\nx^2\n$$");
  });

  it("leaves a closed display block alone", () => {
    const closed = "$$\nx^2\n$$";
    expect(closeOpenMathBlock(closed)).toBe(closed);
  });

  it("ignores $$ lines inside code", () => {
    const code = "```\n$$\n```";
    expect(closeOpenMathBlock(code)).toBe(code);
  });
});

describe("closeOpenBlocks", () => {
  it("normalizes, then closes an open display block", () => {
    expect(closeOpenBlocks("\\(a\\)\n$$\nx")).toBe("$a$\n$$\nx\n$$");
  });

  it("does not count $$ inside a fence it closes", () => {
    expect(closeOpenBlocks("```\n$$")).toBe("```\n$$\n```");
  });

  it("marks an open mermaid block as pending only while streaming", () => {
    const content = "```mermaid\ngraph TD";
    expect(closeOpenBlocks(content, { streaming: true })).toContain(
      "mermaid-pending",
    );
    expect(closeOpenBlocks(content)).not.toContain("mermaid-pending");
  });
});
