import path from "node:path";
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const eslint = new ESLint({ cwd: path.resolve(__dirname, "../..") });

async function restricted(filePath: string, code: string) {
  const [result] = await eslint.lintText(code, { filePath });
  return result.messages.filter((m) => m.ruleId === "no-restricted-syntax");
}

function withClass(className: string): string {
  return `export const a = <div className="${className}" />;`;
}

describe("design token lint rules", () => {
  it.each([
    ["a raw palette color", "bg-blue-500"],
    ["a raw palette color with a variant prefix", "dark:text-emerald-400"],
    ["a raw palette color with an opacity", "border-amber-500/40"],
    ["an arbitrary text size", "text-[10px]"],
    ["a numeric z-index", "z-50"],
    ["an h-N w-N pair", "h-4 w-4"],
    ["a reversed w-N h-N pair", "w-3.5 h-3.5"],
  ])("rejects %s", async (_, className) => {
    expect(
      await restricted("components/example.tsx", withClass(className)),
    ).not.toHaveLength(0);
  });

  it("rejects raw palette colors inside template literals", async () => {
    const code =
      'export const a = (on: boolean) => <div className={`p-1 ${on ? "x" : "y"} text-red-500`} />;';
    expect(await restricted("components/example.tsx", code)).not.toHaveLength(
      0,
    );
  });

  it.each([
    "bg-brand text-brand-foreground",
    "text-white bg-white bg-black/40",
    "size-4 z-overlay text-3xs",
    "h-1.5 w-4",
    "sm:h-4 sm:w-4",
  ])("accepts %s", async (className) => {
    expect(
      await restricted("components/example.tsx", withClass(className)),
    ).toHaveLength(0);
  });

  it("exempts shadcn-generated components/ui from the size rules", async () => {
    expect(
      await restricted(
        "components/ui/example.tsx",
        withClass("z-50 h-4 w-4 text-[0.8rem]"),
      ),
    ).toHaveLength(0);
  });

  it("still rejects raw palette colors in components/ui", async () => {
    expect(
      await restricted("components/ui/example.tsx", withClass("bg-blue-500")),
    ).not.toHaveLength(0);
  });

  it("does not check hex colors", async () => {
    const code = 'export const a = <div style={{ color: "#1e1b4b" }} />;';
    expect(await restricted("app/opengraph-image.tsx", code)).toHaveLength(0);
  });
});
