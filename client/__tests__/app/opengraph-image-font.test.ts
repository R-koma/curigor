import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { HERO_HEADLINE } from "@/components/landing/landing-copy";

// TrueType の cmap 表（format 4）から、フォントが持つ文字のコードポイントを集める
function codePoints(font: Buffer): Set<number> {
  const numTables = font.readUInt16BE(4);
  let cmap = -1;
  for (let i = 0; i < numTables; i++) {
    const record = 12 + i * 16;
    if (font.toString("latin1", record, record + 4) === "cmap") {
      cmap = font.readUInt32BE(record + 8);
    }
  }
  const points = new Set<number>();
  const subtables = font.readUInt16BE(cmap + 2);
  for (let i = 0; i < subtables; i++) {
    const sub = cmap + font.readUInt32BE(cmap + 4 + i * 8 + 4);
    if (font.readUInt16BE(sub) !== 4) continue;
    const segCount = font.readUInt16BE(sub + 6) / 2;
    const ends = sub + 14;
    const starts = ends + segCount * 2 + 2;
    for (let s = 0; s < segCount; s++) {
      const end = font.readUInt16BE(ends + s * 2);
      for (let c = font.readUInt16BE(starts + s * 2); c <= end; c++) {
        if (c !== 0xffff) points.add(c);
      }
    }
  }
  return points;
}

describe("opengraph-image font subset", () => {
  it("has every character the image draws", () => {
    const font = readFileSync(
      path.resolve(__dirname, "../../assets/fonts/noto-sans-jp-bold-og.ttf"),
    );
    const points = codePoints(font);
    const missing = [...new Set(`Curigor${HERO_HEADLINE}`)].filter(
      (ch) => !points.has(ch.codePointAt(0)!),
    );
    expect(missing).toEqual([]);
  });
});
