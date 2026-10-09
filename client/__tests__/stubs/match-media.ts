export const COARSE_POINTER = "(pointer: coarse)";

const matches = new Map<string, boolean>();
const listeners = new Map<string, Set<() => void>>();

export function setMediaQuery(query: string, value: boolean): void {
  matches.set(query, value);
  listeners.get(query)?.forEach((listener) => listener());
}

export function resetMediaQueries(): void {
  matches.clear();
  listeners.clear();
}

export function installMatchMedia(): void {
  window.matchMedia = (query: string): MediaQueryList => {
    const list = {
      get matches() {
        return matches.get(query) ?? false;
      },
      media: query,
      onchange: null,
      addEventListener: (_type: string, listener: () => void) => {
        if (!listeners.has(query)) listeners.set(query, new Set());
        listeners.get(query)!.add(listener);
      },
      removeEventListener: (_type: string, listener: () => void) => {
        listeners.get(query)?.delete(listener);
      },
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    };
    return list as unknown as MediaQueryList;
  };
}
