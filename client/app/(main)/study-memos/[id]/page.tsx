import { headers } from "next/headers";
import { fetchAPI, getToken } from "@/lib/api";
import { StudyMemoEditForm } from "@/components/study-memos/study-memo-edit-form";
import { StudyMemoView } from "@/components/study-memos/study-memo-view";
import type { StudyMemo } from "@/lib/study-memos";

export const dynamic = "force-dynamic";

export default async function StudyMemoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ edit?: string }>;
}) {
  const { id } = await params;
  const { edit } = await searchParams;
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const memo = await fetchAPI<StudyMemo>(`/api/study-memos/${id}`, { token });

  if (edit === "1") {
    return <StudyMemoEditForm key={memo.id} memo={memo} />;
  }
  return <StudyMemoView memo={memo} />;
}
