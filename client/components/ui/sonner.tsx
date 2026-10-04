"use client";

import { useTheme } from "next-themes";
import { useEffect } from "react";
import { Toaster as Sonner, toast, type ToasterProps } from "sonner";
import {
  CircleCheckIcon,
  InfoIcon,
  TriangleAlertIcon,
  OctagonXIcon,
  Loader2Icon,
} from "lucide-react";

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  useEffect(() => {
    const dismissOnOutsideClick = (e: PointerEvent) => {
      if (
        e.target instanceof Element &&
        e.target.closest("[data-sonner-toast]")
      )
        return;
      toast.dismiss();
    };
    document.addEventListener("pointerdown", dismissOnOutsideClick);
    return () =>
      document.removeEventListener("pointerdown", dismissOnOutsideClick);
  }, []);

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      position="top-center"
      duration={5000}
      icons={{
        success: <CircleCheckIcon className="size-4" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4" />,
        error: <OctagonXIcon className="size-4" />,
        loading: <Loader2Icon className="size-4 animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius-xl)",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast !gap-3 !rounded-2xl !border !px-4 !py-3 !shadow-lg",
          title: "!text-sm !font-medium",
          icon: "!mr-0",
          actionButton:
            "!flex !size-8 !items-center !justify-center !rounded-full !bg-foreground !p-0 !text-background hover:!opacity-90",
          error:
            "!border-border !bg-popover !text-popover-foreground [&_[data-icon]]:!size-7 [&_[data-icon]]:!shrink-0 [&_[data-icon]]:!items-center [&_[data-icon]]:!justify-center [&_[data-icon]]:!rounded-full [&_[data-icon]]:!bg-destructive/10 [&_[data-icon]]:!text-destructive dark:[&_[data-icon]]:!bg-destructive/20",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
