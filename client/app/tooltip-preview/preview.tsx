"use client";

import { useState, type ReactNode } from "react";
import { EllipsisIcon, Trash2Icon } from "lucide-react";

import { ChatInput } from "@/components/chat/chat-input";
import { EditResendButton } from "@/components/chat/edit-resend-button";
import { EndSessionButton } from "@/components/chat/end-session-button";
import { LearningProgressIndicator } from "@/components/chat/learning-progress";
import { MessageCopyButton } from "@/components/chat/message-copy-button";
import { MessageSpeechButton } from "@/components/chat/message-speech-button";
import { Sidebar } from "@/components/layout/sidebar";
import { NoteCategoryEditor } from "@/components/notes/note-category-editor";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { TooltipLabel } from "@/components/ui/tooltip";

const USER = { id: "preview", name: "Ryoma", email: "preview@example.com" };

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="text-xs text-muted-foreground">{note}</p>
      </div>
      {children}
    </section>
  );
}

function InputSample({ initial }: { initial: string }) {
  const [value, setValue] = useState(initial);
  return (
    <ChatInput
      value={value}
      onChange={setValue}
      onSend={() => setValue("")}
      isLoading={false}
      sessionId="preview"
    />
  );
}

export function TooltipPreview() {
  const [speaking, setSpeaking] = useState(false);
  return (
    <div className="mx-auto max-w-3xl space-y-10 p-6">
      <header>
        <h1 className="text-lg font-bold">ツールチップの見本</h1>
        <p className="text-sm text-muted-foreground">
          カーソルを乗せるか、Tab キーでフォーカスすると、0.4
          秒後に説明が出ます。続けて別のアイコンに移ると、待たずに出ます。
        </p>
      </header>

      <Section
        title="入力欄"
        note="空のときはマイク、文字を入れると送信が出ます。どちらも説明が出ます。"
      >
        <div className="space-y-4">
          <InputSample initial="" />
          <InputSample initial="二分探索とは" />
        </div>
      </Section>

      <Section
        title="サイドバー"
        note="左上のアイコンにマウスを乗せると開きます。折りたたみ時のリンク・開閉ボタン・カレンダーの前後ボタンに説明が出ます（データが無いので日別のトピックは出ません）。"
      >
        <div className="flex h-[32rem] overflow-hidden rounded-xl border">
          <Sidebar user={USER} />
          <div className="flex-1 bg-muted/30" />
        </div>
      </Section>

      <Section
        title="メッセージ横のボタン"
        note="メッセージにカーソルを乗せるか、Tab で入ると現れます。"
      >
        <div className="group flex items-start gap-3">
          <div className="rounded-2xl bg-muted px-4 py-3">
            二分探索は、探す範囲を毎回半分にします。
          </div>
          <MessageCopyButton content="二分探索は、探す範囲を毎回半分にします。" />
          <MessageSpeechButton
            speaking={speaking}
            onPlay={() => setSpeaking(true)}
            onStop={() => setSpeaking(false)}
          />
          <EditResendButton onClick={() => {}} />
        </div>
      </Section>

      <Section
        title="ノート作成ボタン"
        note="上は強調時（ラベルあり）、下は通常時（アイコンのみ）。"
      >
        <div className="flex items-center gap-4">
          <EndSessionButton highlighted onClick={() => {}} />
          <EndSessionButton highlighted={false} onClick={() => {}} />
        </div>
      </Section>

      <Section
        title="カテゴリー"
        note="「カテゴリーを追加」を押すと、保存とキャンセルが出ます（保存は API を呼ぶので押さないでください）。"
      >
        <NoteCategoryEditor noteId="preview" category={null} />
      </Section>

      <Section
        title="「…」メニュー"
        note="ダッシュボードと学習履歴のカードの右下にあるボタンと同じ組み合わせ（ツールチップとメニューが同じボタンで動く）。"
      >
        <DropdownMenu>
          <TooltipLabel label="その他の操作">
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="その他の操作">
                <EllipsisIcon className="size-4" />
              </Button>
            </DropdownMenuTrigger>
          </TooltipLabel>
          <DropdownMenuContent align="start" className="w-auto">
            <DropdownMenuItem variant="destructive" className="gap-2 px-3">
              <Trash2Icon className="size-4" />
              削除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </Section>

      <Section
        title="学習の進捗"
        note="左は観点なし（Tab で説明が出る）、右は観点あり（クリックでパネル、ホバーで説明）。"
      >
        <div className="flex flex-wrap items-center gap-6">
          <LearningProgressIndicator
            progress={{
              reached_aspects: ["計算量", "前提条件"],
              target_count: 3,
              is_complete: false,
            }}
          />
          <LearningProgressIndicator
            progress={{
              reached_aspects: ["値の埋め込み方"],
              target_count: 3,
              is_complete: false,
              aspects: [
                {
                  name: "値の埋め込み方",
                  is_core: true,
                  reached_stage: "reasoned",
                },
                { name: "書式指定", is_core: false, reached_stage: null },
              ],
            }}
          />
        </div>
      </Section>
    </div>
  );
}
