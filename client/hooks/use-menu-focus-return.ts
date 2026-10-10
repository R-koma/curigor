import { useRef } from "react";

// Radix はメニューを閉じるとトリガーへ focus() を戻すので、マウス・タップで閉じても Chrome は :focus-visible を当てる
export function useMenuFocusReturn() {
  const closedByPointerRef = useRef(false);
  return {
    onPointerUp: () => {
      closedByPointerRef.current = true;
    },
    onPointerDownOutside: () => {
      closedByPointerRef.current = true;
    },
    onKeyDown: () => {
      closedByPointerRef.current = false;
    },
    onCloseAutoFocus: (event: Event) => {
      if (closedByPointerRef.current) event.preventDefault();
      closedByPointerRef.current = false;
    },
  };
}
