import { readFile } from "node:fs/promises";
import path from "node:path";

import { ImageResponse } from "next/og";

import { HERO_HEADLINE } from "@/components/landing/landing-copy";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = `Curigor - ${HERO_HEADLINE}`;

export default async function OpengraphImage() {
  const font = await readFile(
    path.join(process.cwd(), "assets/fonts/noto-sans-jp-bold-og.ttf"),
  );
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 32,
        padding: 80,
        background:
          "linear-gradient(135deg, #172554 0%, #1e3a8a 50%, #1d4ed8 100%)",
        color: "#f1f5f9",
        fontFamily: "Noto Sans JP",
      }}
    >
      <div style={{ fontSize: 80 }}>Curigor</div>
      <div style={{ fontSize: 44, color: "#bfdbfe", textAlign: "center" }}>
        {HERO_HEADLINE}
      </div>
    </div>,
    {
      ...size,
      fonts: [{ name: "Noto Sans JP", data: font, weight: 700 }],
    },
  );
}
