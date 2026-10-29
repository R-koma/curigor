export type SampleTurn = { role: "user" | "assistant"; content: string };

export type SampleDialogue = {
  id: string;
  label: string;
  turns: SampleTurn[];
};

export const sampleDialogues: SampleDialogue[] = [
  {
    id: "sky",
    label: "空の色",
    turns: [
      {
        role: "user",
        content:
          "空が青いのは、太陽の光が空気にぶつかって散らばるからです。青い光ほど散らばりやすいので、空全体が青く見えます。",
      },
      {
        role: "assistant",
        content:
          "青い光ほど散らばりやすい、という点は押さえられています。では、夕焼けが赤く見えるのはなぜでしょう？",
      },
      {
        role: "user",
        content:
          "夕方は光が通る道のりが長いから……？ そこから先がうまく言えません。",
      },
    ],
  },
  {
    id: "interest",
    label: "複利",
    turns: [
      {
        role: "user",
        content:
          "複利は、利息にもさらに利息が付く仕組みです。だから長く預けるほどお金が増えます。",
      },
      {
        role: "assistant",
        content:
          "利息に利息が付く、という点はその通りです。単利と比べて、差が大きく開くのはどんなときですか？",
      },
      {
        role: "user",
        content:
          "期間が長いとき、だと思います。金利が高いときとの違いは説明できません。",
      },
    ],
  },
  {
    id: "soreness",
    label: "筋肉痛",
    turns: [
      {
        role: "user",
        content:
          "筋肉痛は、運動で筋肉に小さな傷ができて、それが治るときに起こる痛みです。",
      },
      {
        role: "assistant",
        content:
          "治る途中の痛み、という捉え方ですね。では、運動した翌日や翌々日になってから痛むのはなぜでしょう？",
      },
      {
        role: "user",
        content: "……どうして遅れて痛むのかは、考えたことがなかったです。",
      },
    ],
  },
  {
    id: "salt",
    label: "塩の役割",
    turns: [
      {
        role: "user",
        content:
          "肉に塩を振ると、塩が水分を引き出すので、身が締まっておいしくなります。",
      },
      {
        role: "assistant",
        content:
          "塩が水分を引き出す、は合っています。では、焼く直前に振るのと、少し前に振っておくのとでは何が変わりますか？",
      },
      {
        role: "user",
        content: "違いはありそうですが、理由までは分かりません。",
      },
    ],
  },
];

export const sampleNote = {
  title: "空が青い理由",
  summary: [
    "太陽の光は、空気の分子にぶつかって四方に散らばる",
    "波長の短い青い光ほど散らばりやすく、空全体が青く見える",
  ],
  explained: ["光が散らばる仕組み", "青い光が散らばりやすいこと"],
  nextToLearn: ["夕焼けが赤く見える理由（光が通る道のりとの関係）"],
  nextReview: "3 日後",
};
