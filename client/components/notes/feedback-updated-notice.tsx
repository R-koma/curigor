"use client";

import { useEffect } from "react";

export function FeedbackUpdatedNotice() {
  useEffect(() => {
    const url = new URL(window.location.href);
    if (!url.searchParams.has("feedback")) return;
    url.searchParams.delete("feedback");
    window.history.replaceState(null, "", url);
  }, []);

  return (
    <p
      role="status"
      className="mb-3 rounded-md bg-success-soft px-3 py-2 text-xs text-success-text"
    >
      復習の結果でフィードバックを更新しました
    </p>
  );
}
