import { Skeleton } from "@/components/ui/skeleton";

export default function ReflectionsLoading() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6 max-md:hidden">
        <Skeleton className="h-7 w-32" />
      </div>
      <div className="md:grid md:grid-cols-[8rem_1fr] md:rounded-2xl md:border md:bg-card">
        <div className="mb-6 flex gap-1 md:mb-0 md:flex-col md:border-r md:p-4">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-10 flex-1 rounded-lg md:h-8" />
          ))}
        </div>
        <div className="space-y-4 md:px-8 md:py-7">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      </div>
    </div>
  );
}
