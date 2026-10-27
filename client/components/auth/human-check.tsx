"use client";

import Script from "next/script";
import {
  type Ref,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";

export const TURNSTILE_SCRIPT_URL =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
export const TOKEN_TIMEOUT_MS = 60_000;

interface Turnstile {
  render(container: HTMLElement, options: Record<string, unknown>): string;
  execute(widgetId: string): void;
  reset(widgetId: string): void;
  remove(widgetId: string): void;
}

declare global {
  interface Window {
    turnstile?: Turnstile;
  }
}

export interface HumanCheckHandle {
  getToken(): Promise<string>;
}

interface Pending {
  resolve(token: string): void;
  reject(error: Error): void;
}

export function HumanCheck({
  siteKey,
  nonce,
  ref,
}: {
  siteKey: string;
  nonce?: string;
  ref?: Ref<HumanCheckHandle>;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);
  const executed = useRef(false);
  const pending = useRef<Pending | null>(null);

  const settle = useCallback((outcome: string | Error) => {
    const current = pending.current;
    pending.current = null;
    if (!current) return;
    if (typeof outcome === "string") current.resolve(outcome);
    else current.reject(outcome);
  }, []);

  const renderWidget = useCallback(() => {
    const turnstile = window.turnstile;
    if (!turnstile || !containerRef.current || widgetId.current) return;
    widgetId.current = turnstile.render(containerRef.current, {
      sitekey: siteKey,
      execution: "execute",
      appearance: "interaction-only",
      theme: "auto",
      language: "ja",
      callback: (token: string) => settle(token),
      "error-callback": () => settle(new Error("Human check failed")),
      "expired-callback": () => {
        executed.current = true;
      },
    });
  }, [siteKey, settle]);

  useEffect(() => {
    renderWidget();
    return () => {
      if (widgetId.current) window.turnstile?.remove(widgetId.current);
      widgetId.current = null;
      executed.current = false;
      settle(new Error("Human check closed"));
    };
  }, [renderWidget, settle]);

  useImperativeHandle(
    ref,
    () => ({
      getToken: () =>
        new Promise<string>((resolve, reject) => {
          const turnstile = window.turnstile;
          const id = widgetId.current;
          if (!turnstile || id === null) {
            reject(new Error("Human check is not ready"));
            return;
          }
          settle(new Error("Superseded"));
          const timer = setTimeout(
            () => settle(new Error("Human check timed out")),
            TOKEN_TIMEOUT_MS,
          );
          pending.current = {
            resolve: (token) => {
              clearTimeout(timer);
              resolve(token);
            },
            reject: (error) => {
              clearTimeout(timer);
              reject(error);
            },
          };
          if (executed.current) turnstile.reset(id);
          executed.current = true;
          turnstile.execute(id);
        }),
    }),
    [settle],
  );

  return (
    <>
      <Script
        src={TURNSTILE_SCRIPT_URL}
        nonce={nonce}
        strategy="afterInteractive"
        onReady={renderWidget}
      />
      <div ref={containerRef} className="flex justify-center empty:hidden" />
    </>
  );
}
