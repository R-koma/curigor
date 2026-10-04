import { headers } from "next/headers";
import { fetchAPI, getToken } from "@/lib/api";
import { SynthesisChat } from "@/components/collections/synthesis-chat";
import type { CollectionDetail } from "@/lib/collections";

export const dynamic = "force-dynamic";

export default async function SynthesisPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const collection = await fetchAPI<CollectionDetail>(
    `/api/collections/${id}`,
    { token },
  );

  return (
    <SynthesisChat
      collectionId={collection.id}
      collectionName={collection.name}
    />
  );
}
