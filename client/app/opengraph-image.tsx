import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Curigor - Learn by Teaching, Powered by AI";

// satori のデフォルトフォントに日本語グリフが無いため、画像内テキストは Latin のみにする
export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 24,
        background:
          "linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%)",
        color: "#f1f5f9",
      }}
    >
      <div style={{ fontSize: 72, fontWeight: 700 }}>Curigor</div>
      <div style={{ fontSize: 32, color: "#c7d2fe" }}>
        Learn by Teaching, Powered by AI
      </div>
    </div>,
    size,
  );
}
