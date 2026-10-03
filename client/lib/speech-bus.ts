export interface AssistantSpeechListener {
  onText: (key: string, text: string) => void;
  onEnd: () => void;
  onAbort: () => void;
}

export interface SpeechBus {
  subscribe: (listener: AssistantSpeechListener) => () => void;
  text: (key: string, text: string) => void;
  end: () => void;
  abort: () => void;
}

export function createSpeechBus(): SpeechBus {
  const listeners = new Set<AssistantSpeechListener>();
  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    text(key, text) {
      listeners.forEach((l) => l.onText(key, text));
    },
    end() {
      listeners.forEach((l) => l.onEnd());
    },
    abort() {
      listeners.forEach((l) => l.onAbort());
    },
  };
}
