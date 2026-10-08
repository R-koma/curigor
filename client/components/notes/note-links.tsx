"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LibraryIcon, Link2Icon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { updateNoteLink, type NoteLink } from "@/lib/note-links";

interface NoteLinksProps {
  noteId: string;
  links: NoteLink[];
}

export function NoteLinks({ noteId, links }: NoteLinksProps) {
  const router = useRouter();
  const [savingId, setSavingId] = useState<string | null>(null);

  if (links.length === 0) {
    return null;
  }

  const update = async (linkId: string, status: "accepted" | "dismissed") => {
    setSavingId(linkId);
    try {
      await updateNoteLink(noteId, linkId, status);
      router.refresh();
    } catch {
      toast.error("つながりを更新できませんでした。もう一度お試しください");
    } finally {
      setSavingId(null);
    }
  };

  const accepted = links.filter((link) => link.status === "accepted");
  const suggested = links.filter((link) => link.status === "suggested");

  return (
    <section id="links" className="scroll-mt-8">
      <div className="mb-4 flex items-center gap-2">
        <Link2Icon className="size-4 text-muted-foreground" />
        <h2 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
          関連するノート
        </h2>
      </div>
      <div className="space-y-6">
        {accepted.length > 0 && (
          <LinkGroup title="つながっているノート">
            {accepted.map((link) => (
              <LinkItem key={link.id} link={link}>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={savingId !== null}
                  onClick={() => update(link.id, "dismissed")}
                >
                  外す
                </Button>
              </LinkItem>
            ))}
          </LinkGroup>
        )}
        {suggested.length > 0 && (
          <LinkGroup
            title="つながりの候補"
            description="別のまとめノートにある、内容の近いノートです"
          >
            {suggested.map((link) => (
              <LinkItem key={link.id} link={link}>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={savingId !== null}
                  onClick={() => update(link.id, "accepted")}
                >
                  つなげる
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={savingId !== null}
                  onClick={() => update(link.id, "dismissed")}
                >
                  つなげない
                </Button>
              </LinkItem>
            ))}
          </LinkGroup>
        )}
      </div>
    </section>
  );
}

function LinkGroup({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="text-sm font-medium">{title}</h3>
      {description && (
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      )}
      <ul className="mt-3 divide-y divide-border rounded-xl border">
        {children}
      </ul>
    </div>
  );
}

function LinkItem({
  link,
  children,
}: {
  link: NoteLink;
  children: React.ReactNode;
}) {
  return (
    <li className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 space-y-1">
        <Link
          href={`/notes/${link.note.id}`}
          className="font-medium break-words hover:underline"
        >
          {link.note.topic}
        </Link>
        {link.note.collection_name && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <LibraryIcon className="size-3.5" aria-hidden />
            {link.note.collection_name}
          </p>
        )}
        {link.note.summary && (
          <p className="line-clamp-2 text-sm text-muted-foreground">
            {link.note.summary}
          </p>
        )}
      </div>
      <div className="flex shrink-0 gap-2">{children}</div>
    </li>
  );
}
