import { Suspense } from "react";
import { SearchSection } from "@/components/SearchSection";
import { ActiveFilterPills } from "@/components/ActiveFilterPills";
import { LabCard } from "@/components/LabCard";
import { fetchLabs } from "@/lib/api";

interface PageProps {
  searchParams: Promise<{
    q?: string;
    institution?: string;
    faculty?: string;
    keyword?: string;
    topics?: string;
    min_publication_count?: string;
    min_citation_count?: string;
    min_h_index?: string;
    sort_by?: string;
    sort_order?: string;
  }>;
}

function SearchIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto text-muted/50">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  );
}

export default async function HomePage({ searchParams }: PageProps) {
  const params = await searchParams;
  const {
    q,
    institution,
    faculty,
    keyword,
    topics: topicsParam,
    min_publication_count,
    min_citation_count,
    min_h_index,
    sort_by,
    sort_order,
  } = params;
  const topic = topicsParam?.trim() ? topicsParam.split(",").map((t) => t.trim()).filter(Boolean) : undefined;
  const filters = {
    q,
    institution,
    faculty,
    keyword,
    topic,
    min_publication_count: min_publication_count ? parseInt(min_publication_count, 10) : undefined,
    min_citation_count: min_citation_count ? parseInt(min_citation_count, 10) : undefined,
    min_h_index: min_h_index ? parseInt(min_h_index, 10) : undefined,
    sort_by: sort_by as "publication_count" | "citation_count" | "h_index" | "last_crawled" | undefined,
    sort_order: sort_order as "asc" | "desc" | undefined,
  };
  let labs: Awaited<ReturnType<typeof fetchLabs>> = [];
  let error: string | null = null;
  const limit = q?.trim() ? 20 : 100;
  try {
    labs = await fetchLabs(filters, limit);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch labs";
  }

  return (
    <div className="space-y-8">
      <Suspense
        fallback={
          <div className="rounded-2xl bg-gradient-to-b from-cream to-slate-50/50 px-6 py-8">
            <div className="mt-4 h-12 animate-pulse rounded-xl bg-slate-200" />
            <div className="mt-4 h-14 animate-pulse rounded-xl bg-slate-100" />
          </div>
        }
      >
        <SearchSection />
      </Suspense>

      {error ? (
        <div className="flex gap-4 rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-800 shadow-soft">
          <span className="text-amber-600">
            <AlertIcon />
          </span>
          <div>
            <p className="font-semibold">Could not connect to backend</p>
            <p className="mt-1 text-sm">{error}</p>
            <p className="mt-3 text-sm">
              Ensure the backend is running (
              <code className="rounded bg-amber-100 px-1.5 py-0.5">uvicorn app.main:app --reload</code>
              ) and{" "}
              <code className="rounded bg-amber-100 px-1.5 py-0.5">DATABASE_URL</code> is set in{" "}
              <code className="rounded bg-amber-100 px-1.5 py-0.5">backend/.env</code>.
            </p>
          </div>
        </div>
      ) : labs.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-soft">
          <SearchIcon />
          <p className="mt-4 font-medium text-navy">No labs found</p>
          <p className="mt-1 text-sm text-muted">
            Try broadening your filters or run ingestion to populate the database.
          </p>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200 pb-4">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-serif text-lg font-semibold text-navy">
                {labs.length} lab{labs.length !== 1 ? "s" : ""} found
              </h2>
              <ActiveFilterPills />
            </div>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {labs.map((lab) => (
              <LabCard key={lab.id} lab={lab} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
