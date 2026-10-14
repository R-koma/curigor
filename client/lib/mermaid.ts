export type DiagramTheme = "default" | "dark";

let queue: Promise<unknown> = Promise.resolve();

export function renderMermaid(
  id: string,
  code: string,
  theme: DiagramTheme,
): Promise<string> {
  const run = async () => {
    const { default: mermaid } = await import("mermaid");
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme });
    try {
      const { svg } = await mermaid.render(id, code);
      return svg;
    } finally {
      // mermaid は描画に失敗すると一時要素 d<id> を body に残す
      document.getElementById(`d${id}`)?.remove();
    }
  };
  // initialize は全体の設定を書き換えるので、描画を 1 つずつ順に行う
  const result = queue.then(run, run);
  queue = result.catch(() => undefined);
  return result;
}
