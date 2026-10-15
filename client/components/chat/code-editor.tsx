"use client";

import { useEffect, useRef, useState } from "react";
import { EditorLoadError } from "@/components/chat/editor-load-error";
import { Spinner } from "@/components/ui/spinner";
import { CODE_LANGUAGES } from "@/lib/code-languages";
import { loadCodeMirror, type CodeMirror } from "@/lib/codemirror";

interface CodeEditorProps {
  fence: string;
  onChange: (code: string) => void;
  onSubmit: () => void;
}

interface Editor {
  cm: CodeMirror;
  view: InstanceType<CodeMirror["EditorView"]>;
  language: InstanceType<CodeMirror["Compartment"]>;
}

type Status = "loading" | "ready" | "failed";

const EDITOR_THEME = {
  "&": { maxHeight: "40dvh", fontSize: "0.875rem" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--font-mono)", overflow: "auto" },
  ".cm-content": { minHeight: "7.5rem", caretColor: "var(--foreground)" },
};

export function CodeEditor({ fence, onChange, onSubmit }: CodeEditorProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<Editor | null>(null);
  const handlers = useRef({ onChange, onSubmit });
  const [status, setStatus] = useState<Status>("loading");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    handlers.current = { onChange, onSubmit };
  });

  useEffect(() => {
    let cancelled = false;
    loadCodeMirror().then(
      (cm) => {
        const host = hostRef.current;
        if (cancelled || !host) return;
        const language = new cm.Compartment();
        const view = new cm.EditorView({
          parent: host,
          state: cm.EditorState.create({
            extensions: [
              cm.history(),
              cm.indentOnInput(),
              // defaultKeymap の Mod-Enter（insertBlankLine）より先に置く
              cm.keymap.of([
                {
                  key: "Mod-Enter",
                  run: () => {
                    handlers.current.onSubmit();
                    return true;
                  },
                },
                cm.indentWithTab,
                ...cm.defaultKeymap,
                ...cm.historyKeymap,
              ]),
              cm.syntaxHighlighting(cm.classHighlighter),
              language.of([]),
              cm.EditorView.updateListener.of((update) => {
                if (update.docChanged) {
                  handlers.current.onChange(update.state.doc.toString());
                }
              }),
              cm.EditorView.contentAttributes.of({ "aria-label": "コード" }),
              cm.EditorView.theme(EDITOR_THEME),
            ],
          }),
        });
        editorRef.current = { cm, view, language };
        view.focus();
        setStatus("ready");
      },
      () => {
        if (!cancelled) setStatus("failed");
      },
    );
    return () => {
      cancelled = true;
      editorRef.current?.view.destroy();
      editorRef.current = null;
    };
  }, [attempt]);

  useEffect(() => {
    const editor = editorRef.current;
    if (status !== "ready" || !editor) return;
    const name = CODE_LANGUAGES.find((l) => l.fence === fence)?.codemirror;
    const description = name
      ? editor.cm.LanguageDescription.matchLanguageName(
          editor.cm.languages,
          name,
        )
      : null;
    if (!description) {
      editor.view.dispatch({ effects: editor.language.reconfigure([]) });
      return;
    }
    let active = true;
    description.load().then(
      (support) => {
        if (active && editorRef.current === editor) {
          editor.view.dispatch({
            effects: editor.language.reconfigure(support),
          });
        }
      },
      () => {},
    );
    return () => {
      active = false;
    };
  }, [fence, status]);

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
    <div className="relative min-h-32 rounded-lg border bg-background">
      {status === "loading" && <Spinner className="absolute top-3 left-3" />}
      <div ref={hostRef} />
    </div>
  );
}
