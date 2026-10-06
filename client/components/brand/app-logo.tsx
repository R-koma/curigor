import { cn } from "@/lib/utils";

const MAIN = "#155DFC";
const SHADE = "#193CB8";
const LINE = "#FFFFFF";

export function AppLogo({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="1.5 7.25 29.75 17.5"
      aria-hidden="true"
      focusable="false"
      className={cn("h-6 w-auto shrink-0", className)}
    >
      <g transform="translate(0 -3)">
        <path d="M6 25.5 A2 2 0 0 0 10 25.5 Z" fill={MAIN} />
        <path d="M18 25.5 A2 2 0 0 0 22 25.5 Z" fill={MAIN} />
        <circle cx="28.3" cy="18.5" r="2.6" fill={MAIN} />
        <g transform="rotate(-8 4 23)" fill={MAIN}>
          <rect x="6" y="15.45" width="1.5" height="1.5" />
          <rect x="4" y="17.45" width="1.5" height="1.5" />
          <rect x="6" y="17.45" width="1.5" height="1.5" />
          <rect x="4" y="19.45" width="1.5" height="1.5" />
          <rect x="6" y="19.45" width="1.5" height="1.5" />
          <rect x="4" y="21.45" width="1.5" height="1.5" />
          <rect x="6" y="21.45" width="1.5" height="1.5" />
          <rect
            x="3.2"
            y="12.9"
            width="1.2"
            height="1.2"
            transform="rotate(20 3.8 13.5)"
          />
          <rect
            x="5.6"
            y="13.1"
            width="1.1"
            height="1.1"
            transform="rotate(-15 6.15 13.65)"
          />
          <rect
            x="4.2"
            y="10.9"
            width="0.9"
            height="0.9"
            transform="rotate(35 4.65 11.35)"
          />
        </g>
        <g fill={SHADE}>
          <rect x="9.7" y="12.85" width="1.8" height="1.8" />
          <rect x="7.5" y="15.05" width="1.8" height="1.8" />
          <rect x="9.7" y="15.05" width="1.8" height="1.8" />
          <rect x="7.5" y="17.25" width="1.8" height="1.8" />
          <rect x="9.7" y="17.25" width="1.8" height="1.8" />
          <rect x="7.5" y="19.45" width="1.8" height="1.8" />
          <rect x="9.7" y="19.45" width="1.8" height="1.8" />
          <rect x="7.5" y="21.65" width="1.8" height="1.35" />
          <rect x="9.7" y="21.65" width="1.8" height="1.35" />
          <rect
            x="7.9"
            y="10.7"
            width="1.4"
            height="1.4"
            transform="rotate(15 8.6 11.4)"
          />
        </g>
        <rect x="11.5" y="12" width="4.5" height="11" rx="0.6" fill={MAIN} />
        <rect x="12.1" y="13.6" width="3.3" height="1.1" fill={LINE} />
        <rect x="12.1" y="20.2" width="3.3" height="1.1" fill={LINE} />
        <rect
          x="16"
          y="12.75"
          width="3.5"
          height="10.25"
          rx="0.6"
          fill={SHADE}
        />
        <rect x="16.6" y="14.35" width="2.3" height="1.1" fill={LINE} />
        <rect x="16.6" y="20.2" width="2.3" height="1.1" fill={LINE} />
        <rect x="19.5" y="15.2" width="4" height="7.8" rx="0.6" fill={MAIN} />
        <rect x="20.1" y="16.8" width="2.8" height="1.1" fill={LINE} />
        <rect x="20.1" y="20.2" width="2.8" height="1.1" fill={LINE} />
        <rect x="2.5" y="23" width="24" height="2.5" rx="1.25" fill={MAIN} />
      </g>
    </svg>
  );
}
