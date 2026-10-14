const SPOKEN_FORMULA = "数式";
const MAX_READING_CHARS = 60;
const ARROW = "→";

class UnsupportedLatex extends Error {}

type Token =
  | { kind: "command"; name: string }
  | { kind: "char"; value: string }
  | { kind: "text"; value: string };

interface Atom {
  reading: string;
  operator?: string;
}

const words = (entries: Record<string, string>) =>
  new Map(Object.entries(entries));

const RAW_TEXT_COMMANDS = new Set(["text", "textrm", "mathrm", "operatorname"]);
const STYLE_COMMANDS = new Set([
  "mathbf",
  "mathit",
  "mathsf",
  "mathcal",
  "mathbb",
  "boldsymbol",
]);
const SILENT_COMMANDS = new Set([
  ",",
  ";",
  ":",
  "!",
  " ",
  "quad",
  "qquad",
  "left",
  "right",
  "displaystyle",
  "big",
  "Big",
  "bigl",
  "bigr",
  "Bigl",
  "Bigr",
]);
const FRACTIONS = new Set(["frac", "dfrac", "tfrac"]);
const PREFIX_ACCENTS = words({ vec: "ベクトル" });
const SUFFIX_ACCENTS = words({
  bar: "バー",
  overline: "バー",
  hat: "ハット",
  tilde: "チルダ",
  dot: "ドット",
  ddot: "ツードット",
});
const BIG_OPERATORS = words({
  sum: "和",
  prod: "積",
  int: "積分",
  oint: "周回積分",
  lim: "極限",
});
const COMMAND_WORDS = words({
  alpha: "アルファ",
  beta: "ベータ",
  gamma: "ガンマ",
  Gamma: "ガンマ",
  delta: "デルタ",
  Delta: "デルタ",
  epsilon: "イプシロン",
  varepsilon: "イプシロン",
  zeta: "ゼータ",
  eta: "イータ",
  theta: "シータ",
  vartheta: "シータ",
  Theta: "シータ",
  iota: "イオタ",
  kappa: "カッパ",
  lambda: "ラムダ",
  Lambda: "ラムダ",
  mu: "ミュー",
  nu: "ニュー",
  xi: "クシー",
  Xi: "クシー",
  pi: "パイ",
  Pi: "パイ",
  rho: "ロー",
  sigma: "シグマ",
  Sigma: "シグマ",
  tau: "タウ",
  upsilon: "ユプシロン",
  phi: "ファイ",
  varphi: "ファイ",
  Phi: "ファイ",
  chi: "カイ",
  psi: "プサイ",
  Psi: "プサイ",
  omega: "オメガ",
  Omega: "オメガ",
  sin: "サイン",
  cos: "コサイン",
  tan: "タンジェント",
  log: "ログ",
  ln: "エルエヌ",
  exp: "エクスポネンシャル",
  max: "マックス",
  min: "ミニマム",
  times: "かける",
  cdot: "かける",
  div: "わる",
  pm: "プラスマイナス",
  mp: "マイナスプラス",
  neq: "ノットイコール",
  ne: "ノットイコール",
  leq: "以下",
  le: "以下",
  geq: "以上",
  ge: "以上",
  approx: "ニアリーイコール",
  equiv: "合同",
  propto: "比例",
  infty: "無限大",
  partial: "ラウンド",
  nabla: "ナブラ",
  hbar: "エイチバー",
  circ: "度",
  degree: "度",
  prime: "プライム",
  ldots: "てんてんてん",
  cdots: "てんてんてん",
  dots: "てんてんてん",
  to: ARROW,
  rightarrow: ARROW,
  Rightarrow: "ならば",
  "{": "かっこ",
  "}": "かっことじ",
  "|": "",
});
const CHAR_WORDS = words({
  "+": "プラス",
  "-": "マイナス",
  "=": "イコール",
  "<": "小なり",
  ">": "大なり",
  "(": "かっこ",
  ")": "かっことじ",
  "[": "かっこ",
  "]": "かっことじ",
  ",": "、",
  "!": "の階乗",
  "'": "プライム",
  "/": "わる",
  "|": "",
  ".": "",
  ":": "",
  ";": "",
  "~": "",
});

function tokenize(tex: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < tex.length) {
    const char = tex[i];
    if (char === "\\") {
      const letters = /^[a-zA-Z]+/.exec(tex.slice(i + 1))?.[0];
      const name = letters ?? tex.charAt(i + 1);
      i += 1 + name.length;
      if (letters && RAW_TEXT_COMMANDS.has(name) && tex[i] === "{") {
        const close = tex.indexOf("}", i);
        if (close === -1) throw new UnsupportedLatex();
        tokens.push({ kind: "text", value: tex.slice(i + 1, close).trim() });
        i = close + 1;
        continue;
      }
      tokens.push({ kind: "command", name });
      continue;
    }
    if (/\s/.test(char)) {
      i++;
      continue;
    }
    const number = /^\d+(?:\.\d+)?/.exec(tex.slice(i))?.[0];
    const value = number ?? char;
    tokens.push({ kind: "char", value });
    i += value.length;
  }
  return tokens;
}

function join(parts: string[]): string {
  return parts.filter(Boolean).join(" ");
}

function readChar(value: string): string {
  const word = CHAR_WORDS.get(value);
  if (word !== undefined) return word;
  if (/^[\p{L}\p{N}][\p{L}\p{N}.]*$/u.test(value)) return value;
  throw new UnsupportedLatex();
}

function withPower(base: string, power: string): string {
  if (power === "度" || power === "プライム") return `${base} ${power}`;
  return `${base} の ${power} 乗`;
}

function readOperator(name: string, sub?: string, sup?: string): string {
  const word = BIG_OPERATORS.get(name) ?? "";
  if (name === "lim" && sub?.includes(ARROW)) {
    const [variable, target] = sub.split(ARROW).map((part) => part.trim());
    return `${variable} が ${target} に近づくときの${word}`;
  }
  if (sub !== undefined && sup !== undefined) {
    return `${sub} から ${sup} までの${word}`;
  }
  if (sub !== undefined) return `${sub} についての${word}`;
  return word;
}

class Reader {
  private pos = 0;

  constructor(private readonly tokens: Token[]) {}

  read(): string {
    return this.sequence();
  }

  private sequence(close?: string): string {
    const parts: string[] = [];
    while (this.pos < this.tokens.length) {
      const token = this.tokens[this.pos];
      if (token.kind === "char" && token.value === close) {
        this.pos++;
        return join(parts);
      }
      if (token.kind === "char" && token.value === "}") {
        throw new UnsupportedLatex();
      }
      parts.push(this.withScripts(this.atom()));
    }
    if (close) throw new UnsupportedLatex();
    return join(parts);
  }

  private next(): Token {
    const token = this.tokens[this.pos++];
    if (!token) throw new UnsupportedLatex();
    return token;
  }

  private peekChar(value: string): boolean {
    const token = this.tokens[this.pos];
    return token?.kind === "char" && token.value === value;
  }

  private argument(): string {
    if (this.peekChar("{")) {
      this.pos++;
      return this.sequence("}");
    }
    const atom = this.atom();
    if (atom.operator) throw new UnsupportedLatex();
    return atom.reading;
  }

  private atom(): Atom {
    const token = this.next();
    if (token.kind === "text") return { reading: token.value };
    if (token.kind === "char") {
      if (token.value === "{") return { reading: this.sequence("}") };
      return { reading: readChar(token.value) };
    }
    return this.command(token.name);
  }

  private command(name: string): Atom {
    if (FRACTIONS.has(name)) {
      const numerator = this.argument();
      const denominator = this.argument();
      return { reading: `${denominator} 分の ${numerator}` };
    }
    if (name === "sqrt") {
      if (this.peekChar("[")) {
        this.pos++;
        const index = this.sequence("]");
        return { reading: `${index} 乗根 ${this.argument()}` };
      }
      return { reading: `ルート ${this.argument()}` };
    }
    const prefix = PREFIX_ACCENTS.get(name);
    if (prefix) return { reading: `${prefix} ${this.argument()}` };
    const suffix = SUFFIX_ACCENTS.get(name);
    if (suffix) return { reading: `${this.argument()} ${suffix}` };
    if (STYLE_COMMANDS.has(name)) return { reading: this.argument() };
    if (BIG_OPERATORS.has(name)) return { reading: "", operator: name };
    if (SILENT_COMMANDS.has(name)) return { reading: "" };
    const word = COMMAND_WORDS.get(name);
    if (word === undefined) throw new UnsupportedLatex();
    return { reading: word };
  }

  private withScripts(atom: Atom): string {
    let sub: string | undefined;
    let sup: string | undefined;
    while (this.peekChar("_") || this.peekChar("^")) {
      const isSub = this.peekChar("_");
      this.pos++;
      const script = this.argument();
      if (isSub) sub = script;
      else sup = script;
    }
    if (atom.operator) return readOperator(atom.operator, sub, sup);
    let reading = atom.reading;
    if (sub !== undefined) reading = `${reading} ${sub}`;
    if (sup !== undefined) reading = withPower(reading, sup);
    return reading;
  }
}

export function latexToSpeech(tex: string): string {
  let reading: string;
  try {
    reading = new Reader(tokenize(tex)).read();
  } catch (error) {
    if (error instanceof UnsupportedLatex) return SPOKEN_FORMULA;
    throw error;
  }
  const spoken = reading.replaceAll(ARROW, "から").replace(/\s+/g, " ").trim();
  return spoken.length > MAX_READING_CHARS ? SPOKEN_FORMULA : spoken;
}
