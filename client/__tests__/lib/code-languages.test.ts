import { afterEach, describe, expect, it, vi } from "vitest";
import { LanguageDescription } from "@codemirror/language";
import { languages } from "@codemirror/language-data";
import { common, createLowlight } from "lowlight";
import {
  CODE_LANGUAGES,
  fenceForVscodeMode,
  readStoredFence,
  storeFence,
} from "@/lib/code-languages";

describe("CODE_LANGUAGES", () => {
  it.each(CODE_LANGUAGES)("$label has a CodeMirror grammar", (language) => {
    expect(
      LanguageDescription.matchLanguageName(languages, language.codemirror),
    ).not.toBeNull();
  });

  it.each(CODE_LANGUAGES)("$label is known to highlight.js", (language) => {
    expect(createLowlight(common).registered(language.highlight)).toBe(true);
  });
});

describe("fenceForVscodeMode", () => {
  it.each([
    ["python", "python"],
    ["typescriptreact", "typescript"],
    ["javascriptreact", "javascript"],
    ["shellscript", "bash"],
    ["cpp", "cpp"],
    ["markdown", ""],
    ["constructor", ""],
  ])("maps %s to 「%s」", (mode, fence) => {
    expect(fenceForVscodeMode(mode)).toBe(fence);
  });
});

describe("stored fence", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("reads back the stored language", () => {
    storeFence("rust");
    expect(readStoredFence()).toBe("rust");
  });

  it("ignores a stored value that is not a language", () => {
    localStorage.setItem("code-language", "cobol");
    expect(readStoredFence()).toBe("");
  });

  it("falls back to no language when storage is unavailable", () => {
    const blocked = () => {
      throw new Error("blocked");
    };
    vi.stubGlobal("localStorage", { getItem: blocked, setItem: blocked });

    expect(() => storeFence("go")).not.toThrow();
    expect(readStoredFence()).toBe("");
  });
});
