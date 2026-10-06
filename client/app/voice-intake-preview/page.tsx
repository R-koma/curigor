import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { VoiceIntakePreview } from "./preview";

export const metadata: Metadata = {
  title: "音声の聞き取りの見本",
  robots: { index: false, follow: false },
};

export default function VoiceIntakePreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <VoiceIntakePreview />;
}
