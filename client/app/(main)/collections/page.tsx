import { EmptyState } from "@/components/ui/empty-state";
import Link from "next/link";
import { headers } from "next/headers";
import { LibraryIcon } from "lucide-react";
import { fetchAPI, getToken } from "@/lib/api";
import type { CollectionSummary } from "@/lib/collections";

export const dynamic = "force-dynamic";

export default async function CollectionsPage() {
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const { collections } = await fetchAPI<{ collections: CollectionSummary[] }>(
    "/api/collections",
    { token },
  );

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6 border-l-4 border-muted-foreground/40 pl-4">
        <h1 className="text-2xl font-bold">まとめ</h1>
      </div>
      {collections.length === 0 ? (
        <EmptyState icon={LibraryIcon} title="まとめノートはありません。" />
      ) : (
        <ul className="space-y-3">
          {collections.map((c) => (
            <li key={c.id}>
              <Link
                href={`/collections/${c.id}`}
                className="flex items-center justify-between rounded-xl border bg-card p-5 transition-colors hover:border-foreground/20"
              >
                <span className="font-semibold">{c.name}</span>
                <span className="text-sm text-muted-foreground">
                  {c.note_count}件のノート
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
