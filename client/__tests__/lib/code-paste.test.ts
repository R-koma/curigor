import { describe, expect, it } from "vitest";
import { codePasteEdit, guessFence, looksLikeCode } from "@/lib/code-paste";

const CODE = {
  python: "def add(a, b):\n    return a + b\n\nprint(add(1, 2))\n",
  javascript: "function greet(name) {\n  return `Hello, ${name}`;\n}\n",
  java: 'public class Main {\n  public static void main(String[] args) {\n    System.out.println("hi");\n  }\n}\n',
  c: '#include <stdio.h>\n\nint main(void) {\n  printf("hi\\n");\n  return 0;\n}\n',
  sql: "SELECT name, age\nFROM users\nWHERE age > 20\nORDER BY age;\n",
  shell: "cd client\nnpm install\nnpm run dev\n",
  "python with Japanese comments":
    "# 合計を求める\ntotal = 0\nfor x in xs:\n    total += x  # 足す\n",
};

const PROSE = {
  "a Japanese paragraph":
    "二分探索は、配列を半分に分けながら探します。\nまず真ん中の値と比べます。",
  "a bulleted list": "- りんご\n- みかん\n- ぶどう",
  "a LaTeX matrix": "\\begin{pmatrix}\na & b \\\\\nc & d\n\\end{pmatrix}",
  "a table": "| 名前 | 年齢 |\n|---|---|\n| 太郎 | 20 |",
  "an English email": "Hi team,\nThanks for the review.\nBest regards,\nTaro",
  "a Japanese email":
    "お世話になっております。\n資料を送ります。\nよろしくお願いします。",
  "English sentences ending with a parenthesis":
    "First, open the file.\nThen run the tests (all of them)",
  "English lines ending with a colon and parentheses":
    "There are two options (A and B):\nOption A is faster (but costs more)",
  "a requirements list": "Requirements:\nPython 3.13 (or later)\nNode 24 (LTS)",
  "Japanese with assignments":
    "まず a = 1 とおく。\n次に b = a + 2 を計算する。",
  "Japanese with a function":
    "ここで f(x) = x^2 とします\nすると f'(x) = 2x になります",
  "Japanese physics": "速度 v = 10 m/s のとき\n距離 d = vt で求まる",
  "bare equations": "E = mc^2\nF = ma",
  "English sentences starting with keywords":
    "if you think about it, it works.\nfor example, this one.",
};

describe("looksLikeCode", () => {
  it.each(Object.entries(CODE))("is true for %s", (_, text) => {
    expect(looksLikeCode(text)).toBe(true);
  });

  it.each(Object.entries(PROSE))("is false for %s", (_, text) => {
    expect(looksLikeCode(text)).toBe(false);
  });

  it("is false for a single line", () => {
    expect(looksLikeCode("x = 1\n")).toBe(false);
  });
});

describe("guessFence", () => {
  it("names Python", () => {
    expect(guessFence(CODE.python)).toBe("python");
  });

  it("names SQL", () => {
    expect(guessFence(CODE.sql)).toBe("sql");
  });

  it("names nothing when unsure", () => {
    expect(guessFence("a\nb")).toBe("");
  });
});

describe("codePasteEdit", () => {
  const at = (position: number) => ({ start: position, end: position });

  it("fences pasted code with the guessed language", () => {
    expect(codePasteEdit("", at(0), CODE.sql, "")?.text).toBe(
      "```sql\nSELECT name, age\nFROM users\nWHERE age > 20\nORDER BY age;\n```\n",
    );
  });

  it("trusts the language VS Code attaches", () => {
    expect(
      codePasteEdit("", at(0), "a\nb", JSON.stringify({ mode: "rust" }))?.text,
    ).toBe("```rust\na\nb\n```\n");
  });

  it("fences VS Code text without a known language as bare code", () => {
    expect(
      codePasteEdit("", at(0), "a\nb", JSON.stringify({ mode: "yaml" }))?.text,
    ).toBe("```\na\nb\n```\n");
  });

  it.each(["markdown", "plaintext", "latex"])(
    "judges VS Code %s text like any other paste",
    (mode) => {
      expect(
        codePasteEdit(
          "",
          at(0),
          PROSE["a Japanese paragraph"],
          JSON.stringify({ mode }),
        ),
      ).toBeNull();
    },
  );

  it("leaves a single line from VS Code alone", () => {
    expect(
      codePasteEdit("", at(0), "x = 1\n", JSON.stringify({ mode: "python" })),
    ).toBeNull();
  });

  it("leaves prose alone", () => {
    expect(
      codePasteEdit("", at(0), PROSE["a Japanese paragraph"], ""),
    ).toBeNull();
  });

  it("leaves text that already has a fence alone", () => {
    expect(codePasteEdit("", at(0), "```\nx = 1\ny = 2\n```", "")).toBeNull();
  });

  it("leaves text that already has a tilde fence alone", () => {
    expect(
      codePasteEdit(
        "",
        at(0),
        "~~~\ndef f():\n    x = 1\n    y = 2\n    return x + y\n~~~",
        "",
      ),
    ).toBeNull();
  });

  it("leaves a paste inside an open fence alone", () => {
    expect(codePasteEdit("```py\n", at(6), CODE.python, "")).toBeNull();
  });

  it("ignores VS Code data that is not JSON", () => {
    expect(codePasteEdit("", at(0), "a\nb", "{broken")).toBeNull();
  });
});
