export const TONES = [
  "brand",
  "success",
  "warning",
  "caution",
  "danger",
  "neutral",
] as const;

export type Tone = (typeof TONES)[number];

export interface ToneClasses {
  text: string;
  soft: string;
  border: string;
  marker: string;
}

export const TONE_CLASSES: Record<Tone, ToneClasses> = {
  brand: {
    text: "text-brand-text",
    soft: "bg-brand-soft",
    border: "border-brand",
    marker: "bg-brand",
  },
  success: {
    text: "text-success-text",
    soft: "bg-success-soft",
    border: "border-success",
    marker: "bg-success",
  },
  warning: {
    text: "text-warning-text",
    soft: "bg-warning-soft",
    border: "border-warning",
    marker: "bg-warning",
  },
  caution: {
    text: "text-caution-text",
    soft: "bg-caution-soft",
    border: "border-caution",
    marker: "bg-caution",
  },
  danger: {
    text: "text-destructive",
    soft: "bg-destructive/10 dark:bg-destructive/20",
    border: "border-destructive",
    marker: "bg-destructive",
  },
  neutral: {
    text: "text-muted-foreground",
    soft: "bg-muted",
    border: "border-border",
    marker: "bg-muted-foreground",
  },
};
