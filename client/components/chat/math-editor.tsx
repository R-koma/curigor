"use client";

import { useEffect, useRef, useState } from "react";
import { EditorLoadError } from "@/components/chat/editor-load-error";
import { Spinner } from "@/components/ui/spinner";
import { loadMathLive, watchKeyboardHeight } from "@/lib/mathlive";

interface MathEditorProps {
  initialValue: string;
  onChange: (latex: string) => void;
  onSubmit: () => void;
  onKeyboardHeight: (height: number) => void;
}

type Status = "loading" | "ready" | "failed";

export function MathEditor({
  initialValue,
  onChange,
  onSubmit,
  onKeyboardHeight,
}: MathEditorProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const handlers = useRef({ onChange, onSubmit, onKeyboardHeight });
  const [initial] = useState(initialValue);
  const [status, setStatus] = useState<Status>("loading");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    handlers.current = { onChange, onSubmit, onKeyboardHeight };
  });

  useEffect(() => {
    let cancelled = false;
    let cleanup = () => {};
    loadMathLive().then(
      ({ MathfieldElement }) => {
        const host = hostRef.current;
        if (cancelled || !host) return;
        const field = new MathfieldElement();
        field.value = initial;
        field.mathVirtualKeyboardPolicy = "auto";
        field.setAttribute("aria-label", "数式");
        field.className =
          "block w-full rounded-lg border bg-background px-2 py-1.5 text-lg";
        const handleInput = () => handlers.current.onChange(field.value);
        const handleBeforeInput = (event: Event) => {
          if ((event as InputEvent).inputType !== "insertLineBreak") return;
          event.preventDefault();
          handlers.current.onSubmit();
        };
        field.addEventListener("input", handleInput);
        field.addEventListener("beforeinput", handleBeforeInput);
        host.appendChild(field);
        const stopWatching = watchKeyboardHeight((height) =>
          handlers.current.onKeyboardHeight(height),
        );
        field.focus();
        cleanup = () => {
          stopWatching();
          field.remove();
        };
        setStatus("ready");
      },
      () => {
        if (!cancelled) setStatus("failed");
      },
    );
    return () => {
      cancelled = true;
      cleanup();
    };
  }, [attempt, initial]);

  if (status === "failed") {
    return (
      <EditorLoadError
        onRetry={() => {
          setStatus("loading");
          setAttempt((count) => count + 1);
        }}
      />
    );
  }
  return (
    <div className="relative min-h-11">
      {status === "loading" && <Spinner className="absolute top-3 left-2" />}
      <div ref={hostRef} />
    </div>
  );
}
