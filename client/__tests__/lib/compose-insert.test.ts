import { describe, expect, it } from "vitest";
import {
  applyEdit,
  findMathAt,
  hasRichContent,
  insertCodeBlock,
  insertMath,
  isInsideFence,
  replaceMath,
} from "@/lib/compose-insert";

const at = (position: number) => ({ start: position, end: position });

describe("insertMath", () => {
  it("adds a space before a formula that follows a word", () => {
    const edit = insertMath("答えは", at(3), "x^2");
    expect(applyEdit("答えは", edit)).toBe("答えは $x^2$");
  });

  it("adds a space after a formula that precedes a word", () => {
    const value = "答えは です";
    expect(applyEdit(value, insertMath(value, at(4), "x"))).toBe(
      "答えは $x$ です",
    );
  });

  it("inserts a bare formula into an empty input", () => {
    expect(insertMath("", at(0), "x")).toEqual({
      start: 0,
      end: 0,
      text: "$x$",
    });
  });

  it("replaces the selected text", () => {
    const value = "a TODO b";
    expect(applyEdit(value, insertMath(value, { start: 2, end: 6 }, "y"))).toBe(
      "a $y$ b",
    );
  });
});

describe("replaceMath", () => {
  it("rewrites the formula in place", () => {
    const value = "面積は $\\pi r^2$ です";
    const span = findMathAt(value, 8)!;
    expect(applyEdit(value, replaceMath(span, "2\\pi r"))).toBe(
      "面積は $2\\pi r$ です",
    );
  });
});

describe("insertCodeBlock", () => {
  it("puts the block on its own lines after text", () => {
    expect(insertCodeBlock("見て", at(2), "print(1)\n", "python")).toEqual({
      start: 2,
      end: 2,
      text: "\n```python\nprint(1)\n```\n",
    });
  });

  it("writes a bare fence without a language", () => {
    expect(insertCodeBlock("", at(0), "x", "").text).toBe("```\nx\n```\n");
  });

  it("does not add a blank line at a line start", () => {
    const value = "a\nb";
    expect(applyEdit(value, insertCodeBlock(value, at(2), "x", ""))).toBe(
      "a\n```\nx\n```\nb",
    );
  });
});

describe("findMathAt", () => {
  it("finds the formula around the cursor", () => {
    expect(findMathAt("面積は $\\pi r^2$ です", 8)).toEqual({
      start: 4,
      end: 13,
      latex: "\\pi r^2",
    });
  });

  it.each([
    ["inline code", "`$x$`", 2],
    ["display math", "$$x$$", 2],
    ["the closing edge", "$x$", 3],
    ["an escaped dollar", "\\$5 と \\$6", 3],
    ["a fence", "```\n$x$\n```", 5],
  ])("ignores %s", (_, value, cursor) => {
    expect(findMathAt(value, cursor)).toBeNull();
  });
});

describe("hasRichContent", () => {
  it.each([
    ["inline math", "$x$"],
    ["display math", "$$\nx\n$$"],
    ["\\( \\)", "\\(x\\)"],
    ["\\[ \\]", "\\[x\\]"],
    ["a fence", "```py\nx"],
  ])("is true for %s", (_, value) => {
    expect(hasRichContent(value)).toBe(true);
  });

  it.each([
    ["plain text", "ただの文です"],
    ["inline code", "`echo $HOME $PATH`"],
    ["escaped dollars", "費用は\\$5と\\$6"],
  ])("is false for %s", (_, value) => {
    expect(hasRichContent(value)).toBe(false);
  });
});

describe("isInsideFence", () => {
  it("is true inside an open fence", () => {
    expect(isInsideFence("```py\nx", 7)).toBe(true);
  });

  it("is false after a closed fence", () => {
    const value = "```\nx\n```\n";
    expect(isInsideFence(value, value.length)).toBe(false);
  });
});
