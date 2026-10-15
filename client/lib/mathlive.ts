let loading: Promise<typeof import("mathlive")> | null = null;

export function loadMathLive(): Promise<typeof import("mathlive")> {
  loading ??= import("mathlive").then(
    (mathlive) => {
      // フォントは app/layout.tsx の katex.min.css が読み込む KaTeX のものを使う
      mathlive.MathfieldElement.fontsDirectory = null;
      mathlive.MathfieldElement.soundsDirectory = null;
      return mathlive;
    },
    (error: unknown) => {
      loading = null;
      throw error;
    },
  );
  return loading;
}

export function watchKeyboardHeight(
  onHeight: (height: number) => void,
): () => void {
  const keyboard = window.mathVirtualKeyboard;
  const update = () =>
    onHeight(keyboard.visible ? keyboard.boundingRect.height : 0);
  keyboard.addEventListener("geometrychange", update);
  keyboard.addEventListener("virtual-keyboard-toggle", update);
  return () => {
    keyboard.removeEventListener("geometrychange", update);
    keyboard.removeEventListener("virtual-keyboard-toggle", update);
    onHeight(0);
  };
}
