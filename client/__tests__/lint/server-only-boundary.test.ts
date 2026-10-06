import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../..");
const SOURCE_DIRS = ["app", "components", "lib", "hooks", "context"];
const SERVER_ONLY_MODULES = [
  "@/lib/auth",
  "@/lib/auth-otp",
  "@/lib/dev-auth",
  "@/lib/email/send-email",
];

function sourceFiles(dir: string): string[] {
  return readdirSync(path.join(ROOT, dir)).flatMap((name) => {
    const relative = path.join(dir, name);
    if (statSync(path.join(ROOT, relative)).isDirectory()) {
      return sourceFiles(relative);
    }
    return /\.(ts|tsx)$/.test(relative) ? [relative] : [];
  });
}

const files = SOURCE_DIRS.flatMap(sourceFiles).map((file) => ({
  file,
  code: readFileSync(path.join(ROOT, file), "utf8"),
}));

const clientFiles = files.filter(({ code }) =>
  /^\s*["']use client["']/.test(code),
);

function importsModule(code: string, specifier: string): boolean {
  const escaped = specifier.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
  return new RegExp(`from\\s+["']${escaped}["']`).test(code);
}

describe("server-only modules", () => {
  it("are never imported from client components", () => {
    expect(files.length).toBeGreaterThan(0);
    expect(clientFiles.length).toBeGreaterThan(0);
    const offenders = clientFiles.flatMap(({ file, code }) =>
      SERVER_ONLY_MODULES.filter((m) => importsModule(code, m)).map(
        (m) => `${file} -> ${m}`,
      ),
    );
    expect(offenders).toEqual([]);
  });

  it("keep the dev switches out of NEXT_PUBLIC_ variables", () => {
    const offenders = files
      .filter(({ code }) => /NEXT_PUBLIC_DEV_/.test(code))
      .map(({ file }) => file);
    expect(offenders).toEqual([]);
  });
});
