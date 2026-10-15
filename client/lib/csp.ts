const DEFAULT_API_URL = "http://localhost:8000";
const DEFAULT_WS_URL = "ws://localhost:8000";
const DEFAULT_AUTH_URL = "http://localhost:3000";

function toOrigin(url: string): string | null {
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

function connectSources(): string[] {
  const origins = [
    process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL,
    process.env.NEXT_PUBLIC_WS_URL || DEFAULT_WS_URL,
    process.env.NEXT_PUBLIC_BETTER_AUTH_URL || DEFAULT_AUTH_URL,
  ]
    .map(toOrigin)
    .filter((origin): origin is string => origin !== null);
  return ["'self'", ...new Set(origins)];
}

export function buildCsp({
  nonce,
  isDev,
}: {
  nonce: string;
  isDev: boolean;
}): string {
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": [
      "'self'",
      `'nonce-${nonce}'`,
      "'strict-dynamic'",
      "'wasm-unsafe-eval'",
      ...(isDev ? ["'unsafe-eval'"] : []),
    ],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "blob:", "data:", "https://*.googleusercontent.com"],
    "font-src": ["'self'", "data:"],
    "connect-src": connectSources(),
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'self'"],
  };
  return Object.entries(directives)
    .map(([name, sources]) => `${name} ${sources.join(" ")}`)
    .join("; ");
}

export function cspHeaderName(
  enforce: boolean,
): "Content-Security-Policy" | "Content-Security-Policy-Report-Only" {
  return enforce
    ? "Content-Security-Policy"
    : "Content-Security-Policy-Report-Only";
}
