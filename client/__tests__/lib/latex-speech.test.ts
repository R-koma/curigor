import { describe, expect, it } from "vitest";
import { latexToSpeech } from "@/lib/latex-speech";

describe("latexToSpeech", () => {
  it.each([
    ["\\frac{a}{b}", "b 分の a"],
    ["\\dfrac{1}{2}", "2 分の 1"],
    ["x^2", "x の 2 乗"],
    ["x^{-1}", "x の マイナス 1 乗"],
    ["a_n", "a n"],
    ["\\sqrt{x}", "ルート x"],
    ["\\sqrt[3]{x}", "3 乗根 x"],
    ["\\sum_{i=1}^{n} i", "i イコール 1 から n までの和 i"],
    ["\\int_a^b f(x)\\,dx", "a から b までの積分 f かっこ x かっことじ d x"],
    [
      "\\lim_{x \\to 0} \\frac{\\sin x}{x}",
      "x が 0 に近づくときの極限 x 分の サイン x",
    ],
    ["a + b - c", "a プラス b マイナス c"],
    ["2 \\times 3 \\cdot 4 \\div 6", "2 かける 3 かける 4 わる 6"],
    ["x \\pm 1", "x プラスマイナス 1"],
    ["a = b \\neq c", "a イコール b ノットイコール c"],
    ["x \\leq 1 \\geq 0", "x 以下 1 以上 0"],
    ["x < y > z", "x 小なり y 大なり z"],
    ["\\pi \\approx 3.14", "パイ ニアリーイコール 3.14"],
    ["\\alpha + \\beta = \\gamma", "アルファ プラス ベータ イコール ガンマ"],
    ["\\infty", "無限大"],
    ["\\partial f", "ラウンド f"],
    ["\\sin x + \\cos y", "サイン x プラス コサイン y"],
    ["\\tan z", "タンジェント z"],
    ["\\log x", "ログ x"],
    ["\\vec{v}", "ベクトル v"],
    ["\\bar{x}", "x バー"],
    ["\\dot{x}", "x ドット"],
    [
      "\\text{速さ} = \\frac{\\text{距離}}{\\text{時間}}",
      "速さ イコール 時間 分の 距離",
    ],
    ["\\mathrm{d}x", "d x"],
    ["\\mathbf{F} = m\\mathbf{a}", "F イコール m a"],
    ["\\left( a \\right)", "かっこ a かっことじ"],
    ["a \\quad b \\, c", "a b c"],
    ["90^\\circ", "90 度"],
    ["n!", "n の階乗"],
    ["f'(x)", "f プライム かっこ x かっことじ"],
  ])("reads %s as 「%s」", (tex, reading) => {
    expect(latexToSpeech(tex)).toBe(reading);
  });

  it.each([
    ["an environment", "\\begin{pmatrix} a & b \\end{pmatrix}"],
    ["an unknown command", "\\unknowncommand{x}"],
    ["a script without its argument", "x^"],
    ["an unclosed group", "{x"],
    ["a stray closing brace", "x}"],
    ["an alignment mark", "a & b"],
  ])("reads %s as 数式", (_, tex) => {
    expect(latexToSpeech(tex)).toBe("数式");
  });

  it("reads a formula whose reading is too long as 数式", () => {
    const tex = "a + b + c + d + e + f + g + h + i + j + k + l + m";
    expect(latexToSpeech(tex)).toBe("数式");
  });

  it("reads spacing only as an empty string", () => {
    expect(latexToSpeech("\\,")).toBe("");
  });

  it("does not resolve object prototype keys as commands", () => {
    expect(latexToSpeech("\\constructor")).toBe("数式");
  });
});
