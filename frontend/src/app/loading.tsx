function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-slate-200 bg-white p-5 shadow-md">
      <div className="h-5 w-2/3 rounded bg-slate-200" />
      <div className="mt-2 h-4 w-1/2 rounded bg-slate-100" />
      <div className="mt-3 h-4 w-full rounded bg-slate-100" />
      <div className="mt-3 h-4 w-4/5 rounded bg-slate-100" />
      <div className="mt-4 flex gap-2">
        <div className="h-6 w-16 rounded bg-slate-100" />
        <div className="h-6 w-20 rounded bg-slate-100" />
      </div>
    </div>
  );
}

export default function Loading() {
  return (
    <div className="space-y-8">
      <div className="rounded-2xl bg-gradient-to-b from-cream to-slate-50/50 px-6 py-8">
        <div className="text-center">
          <div className="mx-auto h-8 w-3/4 animate-pulse rounded bg-slate-200" />
        </div>
        <div className="mt-6 h-14 animate-pulse rounded-xl bg-slate-200" />
        <div className="mt-4 h-14 animate-pulse rounded-xl bg-slate-100" />
      </div>
      <div className="h-6 w-32 animate-pulse rounded bg-slate-200" />
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  );
}
