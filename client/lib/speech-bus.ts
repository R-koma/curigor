export interface AssistantSpeechListener {
  onText: (text: string) => void;
  onEnd: () => void;
}

export interface SpeechBus {
  subscribe: (listener: AssistantSpeechListener) => () => void;
  text: (text: string) => void;
  end: () => void;
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
    text(text) {
      listeners.forEach((l) => l.onText(text));
    },
    end() {
      listeners.forEach((l) => l.onEnd());
    },
  };
}
