"use client";

import * as React from "react";
import { Dialog as SheetPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

function Sheet({ ...props }: React.ComponentProps<typeof SheetPrimitive.Root>) {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />;
}

function SheetTrigger({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Trigger>) {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />;
}

function SheetClose({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Close>) {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />;
}

function SheetTitle({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Title>) {
  return (
    <SheetPrimitive.Title
      data-slot="sheet-title"
      className={cn("text-base font-semibold", className)}
      {...props}
    />
  );
}

function SheetContent({
  className,
  children,
  side = "left",
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & {
  side?: "left" | "bottom";
}) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay
        data-slot="sheet-overlay"
        className="fixed inset-0 z-50 bg-black/30 duration-200 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0 md:hidden"
      />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        aria-describedby={undefined}
        className={cn(
          "fixed z-50 flex flex-col bg-background shadow-lg duration-200 outline-none data-open:animate-in data-closed:animate-out md:hidden",
          side === "left"
            ? "inset-y-0 left-0 w-[min(75vw,18rem)] border-r pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] data-open:slide-in-from-left data-closed:slide-out-to-left"
            : "inset-x-0 bottom-0 max-h-[85dvh] rounded-t-2xl border-t pb-[max(1rem,env(safe-area-inset-bottom))] data-open:slide-in-from-bottom data-closed:slide-out-to-bottom",
          className,
        )}
        {...props}
      >
        {children}
        <SheetPrimitive.Close className="sr-only">閉じる</SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  );
}

export { Sheet, SheetClose, SheetContent, SheetTitle, SheetTrigger };
