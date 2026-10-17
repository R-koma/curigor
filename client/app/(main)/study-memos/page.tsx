import { headers } from "next/headers";
import { fetchAPI, getToken } from "@/lib/api";
import { PAGE_TITLES } from "@/lib/nav-links";
import type { StudyMemoSummary } from "@/lib/study-memos";
import { PageHeading } from "@/components/layout/page-heading";
import { StudyMemoList } from "@/components/study-memos/study-memo-list";

export const dynamic = "force-dynamic";

export default async function StudyMemosPage() {
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const { memos } = await fetchAPI<{ memos: StudyMemoSummary[] }>(
    "/api/study-memos",
    { token },
  );

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6">
        <PageHeading
          title={PAGE_TITLES["/study-memos"]}
          description={`学習メモ ${memos.length} 件`}
        />
      </div>
      <StudyMemoList memos={memos} />
    </div>
  );
}
