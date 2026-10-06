import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import prettier from "eslint-config-prettier";

const PALETTE =
  "\\b(bg|text|border|ring|fill|stroke|from|to|via|shadow|outline|decoration|placeholder|caret|divide)-(red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-\\d{2,3}";
const ARBITRARY_TEXT = "\\btext-\\[[0-9.]+(rem|px)\\]";
const NUMERIC_Z = "(?<![\\w:-])z-\\d+(?![\\w-])";
const SIZE_PAIR =
  "(?<![\\w:\\[-])(h-([0-9.]+) w-\\2|w-([0-9.]+) h-\\3)(?![\\w-])";

function restrict(pattern, message) {
  return [
    { selector: `Literal[value=/${pattern}/]`, message },
    { selector: `TemplateElement[value.raw=/${pattern}/]`, message },
  ];
}

const COLOR_RULES = restrict(
  PALETTE,
  "色相のある Tailwind の色名は直書きしない。app/globals.css のトークン（bg-brand / text-success-text / bg-destructive など）か lib/tone.ts を使う",
);
const SIZE_RULES = [
  ...restrict(
    ARBITRARY_TEXT,
    "任意値の文字サイズは使わない。text-3xs / text-2xs / text-xs / text-sm / text-prose から選ぶ",
  ),
  ...restrict(
    NUMERIC_Z,
    "数値の z-index は使わない。z-raised / z-menu / z-drawer / z-overlay から選ぶ",
  ),
  ...restrict(SIZE_PAIR, "幅と高さが同じ値の h-N w-N は size-N と書く"),
];

const TITLE_RULES = [
  {
    selector:
      "JSXOpeningElement[name.name=/^(button|Button|a|Link|div|span)$/] > JSXAttribute[name.name='title']",
    message:
      "title 属性は使わない（キーボードとタッチで出ず、見た目も揃わない）。アイコンだけのボタンは aria-label を付けて TooltipLabel（components/ui/tooltip.tsx）で説明する",
  },
];

const SOURCE = "{app,components,lib,hooks,context}/**/*.{ts,tsx}";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  prettier,
  {
    files: [SOURCE],
    rules: {
      "no-restricted-syntax": ["error", ...COLOR_RULES, ...TITLE_RULES],
    },
  },
  {
    files: [SOURCE],
    ignores: ["components/ui/**"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...COLOR_RULES,
        ...SIZE_RULES,
        ...TITLE_RULES,
      ],
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);

export default eslintConfig;
