export interface CodeLanguage {
  label: string;
  fence: string;
  codemirror: string;
  highlight: string;
}

export const CODE_LANGUAGES: readonly CodeLanguage[] = [
  {
    label: "Python",
    fence: "python",
    codemirror: "Python",
    highlight: "python",
  },
  {
    label: "JavaScript",
    fence: "javascript",
    codemirror: "JavaScript",
    highlight: "javascript",
  },
  {
    label: "TypeScript",
    fence: "typescript",
    codemirror: "TypeScript",
    highlight: "typescript",
  },
  { label: "Java", fence: "java", codemirror: "Java", highlight: "java" },
  { label: "C", fence: "c", codemirror: "C", highlight: "c" },
  { label: "C++", fence: "cpp", codemirror: "C++", highlight: "cpp" },
  { label: "Go", fence: "go", codemirror: "Go", highlight: "go" },
  { label: "Rust", fence: "rust", codemirror: "Rust", highlight: "rust" },
  { label: "SQL", fence: "sql", codemirror: "SQL", highlight: "sql" },
  { label: "HTML", fence: "html", codemirror: "HTML", highlight: "xml" },
  { label: "CSS", fence: "css", codemirror: "CSS", highlight: "css" },
  { label: "Bash", fence: "bash", codemirror: "Shell", highlight: "bash" },
];

const STORAGE_KEY = "code-language";
const VSCODE_MODES = new Map([
  ["javascriptreact", "javascript"],
  ["typescriptreact", "typescript"],
  ["shellscript", "bash"],
]);

function isFence(fence: string): boolean {
  return CODE_LANGUAGES.some((language) => language.fence === fence);
}

export function fenceForVscodeMode(mode: string): string {
  const fence = VSCODE_MODES.get(mode) ?? mode;
  return isFence(fence) ? fence : "";
}

export function readStoredFence(): string {
  try {
    const stored = localStorage.getItem(STORAGE_KEY) ?? "";
    return isFence(stored) ? stored : "";
  } catch {
    return "";
  }
}

export function storeFence(fence: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, fence);
  } catch {}
}
