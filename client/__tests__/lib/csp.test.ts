import { afterEach, describe, expect, it, vi } from "vitest";

import { buildCsp, cspHeaderName } from "@/lib/csp";

function directive(csp: string, name: string): string[] {
  const entry = csp
    .split("; ")
    .map((part) => part.split(" "))
    .find(([directiveName]) => directiveName === name);
  if (!entry) throw new Error(`missing directive: ${name}`);
  return entry.slice(1);
}

describe("buildCsp", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("allows scripts only through the nonce, WebAssembly for the voice activity model, and the Turnstile widget", () => {
    const csp = buildCsp({ nonce: "abc123", isDev: false });
    expect(directive(csp, "script-src")).toEqual([
      "'self'",
      "'nonce-abc123'",
      "'strict-dynamic'",
      "'wasm-unsafe-eval'",
      "https://challenges.cloudflare.com",
    ]);
  });

  it("lets the Turnstile widget load its frame", () => {
    const csp = buildCsp({ nonce: "abc123", isDev: false });
    expect(directive(csp, "frame-src")).toEqual([
      "https://challenges.cloudflare.com",
    ]);
  });

  it("adds unsafe-eval only in development", () => {
    const csp = buildCsp({ nonce: "abc123", isDev: true });
    expect(directive(csp, "script-src")).toContain("'unsafe-eval'");
  });

  it("sets the fixed directives", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com/api/");
    const csp = buildCsp({ nonce: "abc123", isDev: false });
    expect(directive(csp, "default-src")).toEqual(["'self'"]);
    expect(directive(csp, "style-src")).toEqual(["'self'", "'unsafe-inline'"]);
    expect(directive(csp, "img-src")).toEqual([
      "'self'",
      "blob:",
      "data:",
      "https://*.googleusercontent.com",
      "https://api.example.com",
    ]);
    expect(directive(csp, "font-src")).toEqual(["'self'", "data:"]);
    expect(directive(csp, "object-src")).toEqual(["'none'"]);
    expect(directive(csp, "base-uri")).toEqual(["'self'"]);
    expect(directive(csp, "form-action")).toEqual(["'self'"]);
    expect(directive(csp, "frame-ancestors")).toEqual(["'self'"]);
  });

  it("does not set a report destination", () => {
    const csp = buildCsp({ nonce: "abc123", isDev: false });
    expect(csp).not.toMatch(/report-(to|uri)/);
  });

  it("connects to the local defaults when the URLs are not set", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NEXT_PUBLIC_WS_URL", "");
    vi.stubEnv("NEXT_PUBLIC_BETTER_AUTH_URL", "");
    const csp = buildCsp({ nonce: "abc123", isDev: false });
    expect(directive(csp, "connect-src")).toEqual([
      "'self'",
      "http://localhost:8000",
      "ws://localhost:8000",
      "http://localhost:3000",
      "https://challenges.cloudflare.com",
    ]);
  });

  it("connects to the origins of the configured URLs", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com/api/");
    vi.stubEnv("NEXT_PUBLIC_WS_URL", "wss://api.example.com");
    vi.stubEnv("NEXT_PUBLIC_BETTER_AUTH_URL", "https://app.example.com/");
    const csp = buildCsp({ nonce: "abc123", isDev: false });
    expect(directive(csp, "connect-src")).toEqual([
      "'self'",
      "https://api.example.com",
      "wss://api.example.com",
      "https://app.example.com",
      "https://challenges.cloudflare.com",
    ]);
  });

  it("lists an origin once when URLs share it", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://app.example.com/backend");
    vi.stubEnv("NEXT_PUBLIC_WS_URL", "wss://app.example.com");
    vi.stubEnv("NEXT_PUBLIC_BETTER_AUTH_URL", "https://app.example.com");
    const csp = buildCsp({ nonce: "abc123", isDev: false });
    expect(directive(csp, "connect-src")).toEqual([
      "'self'",
      "https://app.example.com",
      "wss://app.example.com",
      "https://challenges.cloudflare.com",
    ]);
  });

  it("drops a URL that cannot be parsed instead of throwing", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "not a url");
    vi.stubEnv("NEXT_PUBLIC_WS_URL", "wss://api.example.com");
    vi.stubEnv("NEXT_PUBLIC_BETTER_AUTH_URL", "https://app.example.com");
    const csp = buildCsp({ nonce: "abc123", isDev: false });
    expect(directive(csp, "connect-src")).toEqual([
      "'self'",
      "wss://api.example.com",
      "https://app.example.com",
      "https://challenges.cloudflare.com",
    ]);
  });
});

describe("cspHeaderName", () => {
  it("reports only unless enforced", () => {
    expect(cspHeaderName(false)).toBe("Content-Security-Policy-Report-Only");
    expect(cspHeaderName(true)).toBe("Content-Security-Policy");
  });
});
