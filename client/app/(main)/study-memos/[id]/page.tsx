import { headers } from "next/headers";
import { fetchAPI, getToken } from "@/lib/api";
import { StudyMemoView } from "@/components/study-memos/study-memo-view";
import type { StudyMemo } from "@/lib/study-memos";

export const dynamic = "force-dynamic";

export default async function StudyMemoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const memo = await fetchAPI<StudyMemo>(`/api/study-memos/${id}`, { token });

  return <StudyMemoView memo={memo} />;
}
