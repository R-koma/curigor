"use client";

import { useState } from "react";

import { DeleteAccountDialog } from "@/components/layout/delete-account-dialog";
import { Button } from "@/components/ui/button";

interface DeleteAccountSectionProps {
  email: string;
}

export function DeleteAccountSection({ email }: DeleteAccountSectionProps) {
  const [open, setOpen] = useState(false);

  return (
    <section
      aria-labelledby="delete-account-heading"
      className="space-y-3 rounded-xl border border-destructive/40 p-5"
    >
      <h2 id="delete-account-heading" className="font-semibold">
        アカウントの削除
      </h2>
      <p className="text-sm text-muted-foreground">
        アカウントと、ノート・まとめノート・学習メモ・対話の履歴・画像がすべて削除されます。元に戻せません
      </p>
      <Button variant="destructive" onClick={() => setOpen(true)}>
        アカウントを削除
      </Button>
      <DeleteAccountDialog email={email} open={open} onOpenChange={setOpen} />
    </section>
  );
}
