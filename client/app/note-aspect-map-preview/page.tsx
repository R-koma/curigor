import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { NoteAspectMapPreview } from "./preview";

export const metadata: Metadata = {
  title: "ノートの観点マップの見本",
  robots: { index: false, follow: false },
};

export default function NoteAspectMapPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <NoteAspectMapPreview />;
}
