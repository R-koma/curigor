import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { PageHelpSlot } from "@/components/hints/page-help-slot";
import {
  NavbarSlotProvider,
  useNavbarSlot,
} from "@/context/navbar-slot-context";

function Probe() {
  const { pageHelpIds } = useNavbarSlot();
  return <div data-testid="ids">{JSON.stringify(pageHelpIds)}</div>;
}

function Tree({ withSlot }: { withSlot: boolean }) {
  return (
    <NavbarSlotProvider>
      {withSlot && <PageHelpSlot ids={["dashboard"]} />}
      <Probe />
    </NavbarSlotProvider>
  );
}

describe("PageHelpSlot", () => {
  it("publishes the ids while mounted and clears them on unmount", () => {
    const { getByTestId, rerender } = render(<Tree withSlot />);
    expect(getByTestId("ids").textContent).toBe('["dashboard"]');
    rerender(<Tree withSlot={false} />);
    expect(getByTestId("ids").textContent).toBe("null");
  });
});
