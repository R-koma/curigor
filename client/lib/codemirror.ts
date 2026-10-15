export async function loadCodeMirror() {
  const [state, view, commands, language, data, highlight] = await Promise.all([
    import("@codemirror/state"),
    import("@codemirror/view"),
    import("@codemirror/commands"),
    import("@codemirror/language"),
    import("@codemirror/language-data"),
    import("@lezer/highlight"),
  ]);
  return {
    EditorState: state.EditorState,
    Compartment: state.Compartment,
    EditorView: view.EditorView,
    keymap: view.keymap,
    history: commands.history,
    historyKeymap: commands.historyKeymap,
    defaultKeymap: commands.defaultKeymap,
    indentWithTab: commands.indentWithTab,
    indentOnInput: language.indentOnInput,
    syntaxHighlighting: language.syntaxHighlighting,
    LanguageDescription: language.LanguageDescription,
    languages: data.languages,
    classHighlighter: highlight.classHighlighter,
  };
}

export type CodeMirror = Awaited<ReturnType<typeof loadCodeMirror>>;
