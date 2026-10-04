import { Spinner } from "@/components/ui/spinner";

export function LoadingOverlay({ message }: { message: string }) {
  return (
    <div
      role="status"
      className="fixed inset-0 z-overlay flex items-center justify-center bg-black/40 backdrop-blur-xs"
    >
      <div className="flex flex-col items-center gap-4 rounded-xl border bg-background px-8 py-6 shadow-lg">
        <Spinner size="lg" className="text-primary" />
        <p className="text-base font-medium">{message}</p>
      </div>
    </div>
  );
}
