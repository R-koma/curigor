import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { VoicePanelPreview } from "./preview";

export const metadata: Metadata = {
  title: "音声パネルの見本",
  robots: { index: false, follow: false },
};

export default function VoicePanelPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <VoicePanelPreview />;
}
