"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { UNIVERSITIES, UNIVERSITY_NAMES } from "@/lib/universities";

const DEBOUNCE_MS = 400;

type SortBy = "publication_count" | "citation_count" | "h_index" | "last_crawled" | "";

function ChevronDown({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={`transition-transform duration-300 ${open ? "rotate-180" : ""}`}
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export function SearchFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const institution = searchParams.get("institution") ?? "";
  const faculty = searchParams.get("faculty") ?? "";
  const keyword = searchParams.get("keyword") ?? "";
  const sortBy = (searchParams.get("sort_by") as SortBy) ?? "";
  const sortOrder = searchParams.get("sort_order") ?? "desc";
  const minPub = searchParams.get("min_publication_count") ?? "";
  const minCit = searchParams.get("min_citation_count") ?? "";
  const minH = searchParams.get("min_h_index") ?? "";

  const [expanded, setExpanded] = useState(false);
  const [inst, setInst] = useState(institution);
  const [fac, setFac] = useState(faculty);
  const [kw, setKw] = useState(keyword);
  const [sb, setSb] = useState(sortBy);
  const [so, setSo] = useState(sortOrder);
  const [mp, setMp] = useState(minPub);
  const [mc, setMc] = useState(minCit);
  const [mh, setMh] = useState(minH);
  const isSyncing = useRef(false);

  const activeCount = [
    inst,
    fac,
    kw,
    sb,
    mp,
    mc,
    mh,
  ].filter(Boolean).length;

  useEffect(() => {
    isSyncing.current = true;
    setInst(institution);
    setFac(faculty);
    setKw(keyword);
    setSb(sortBy);
    setSo(sortOrder);
    setMp(minPub);
    setMc(minCit);
    setMh(minH);
  }, [institution, faculty, keyword, sortBy, sortOrder, minPub, minCit, minH]);

  const updateUrl = useCallback(
    (updates: Record<string, string | number | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [k, v] of Object.entries(updates)) {
        const s = typeof v === "number" ? String(v) : (v ?? "").toString().trim();
        if (s) params.set(k, s);
        else params.delete(k);
      }
      router.push(`/?${params.toString()}`);
    },
    [router, searchParams]
  );

  useEffect(() => {
    if (isSyncing.current) {
      isSyncing.current = false;
      return;
    }
    const t = setTimeout(() => {
      if (
        inst !== institution ||
        fac !== faculty ||
        kw !== keyword ||
        sb !== sortBy ||
        so !== sortOrder ||
        mp !== minPub ||
        mc !== minCit ||
        mh !== minH
      ) {
        const minPubNum = mp ? parseInt(mp, 10) : undefined;
        const minCitNum = mc ? parseInt(mc, 10) : undefined;
        const minHNum = mh ? parseInt(mh, 10) : undefined;
        updateUrl({
          institution: inst,
          faculty: fac,
          keyword: kw,
          sort_by: sb || undefined,
          sort_order: so,
          min_publication_count: minPubNum,
          min_citation_count: minCitNum,
          min_h_index: minHNum,
        });
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [inst, fac, kw, sb, so, mp, mc, mh]);

  const handleInstitutionChange = (value: string) => {
    updateUrl({ institution: value, faculty: "" });
  };

  const handleFacultyChange = (value: string) => {
    updateUrl({ institution: inst, faculty: value });
  };

  const faculties = inst ? (UNIVERSITIES[inst] ?? []) : [];

  const selectClass =
    "rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-navy shadow-soft focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";
  const inputClass =
    "rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-navy shadow-soft placeholder-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";
  const metricInputClass =
    "w-16 rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm text-navy shadow-soft focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

  return (
    <div className="rounded-xl border border-slate-200 bg-white/80 p-4 shadow-soft">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-navy hover:bg-slate-50 transition-colors"
        aria-expanded={expanded}
      >
        <span>
          Filters {activeCount > 0 && `(${activeCount})`}
        </span>
        <ChevronDown open={expanded} />
      </button>
      <div
        className={`grid overflow-hidden transition-all duration-300 ease-in-out ${
          expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="min-h-0">
          <div className="mt-4 space-y-6 border-t border-slate-100 pt-4">
            {/* University */}
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                University
              </h3>
              <div className="flex flex-wrap gap-3">
                <select
                  value={inst}
                  onChange={(e) => handleInstitutionChange(e.target.value)}
                  className={selectClass}
                >
                  <option value="">All universities</option>
                  {UNIVERSITY_NAMES.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
                {inst ? (
                  <select
                    value={fac}
                    onChange={(e) => handleFacultyChange(e.target.value)}
                    className={selectClass}
                  >
                    <option value="">All faculties</option>
                    {faculties.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    placeholder="Faculty / Department"
                    value={fac}
                    onChange={(e) => setFac(e.target.value)}
                    className={inputClass}
                  />
                )}
              </div>
            </div>

            {/* Search */}
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                Keyword
              </h3>
              <input
                type="text"
                placeholder="Filter by keyword..."
                value={kw}
                onChange={(e) => setKw(e.target.value)}
                className={`${inputClass} min-w-[200px]`}
              />
            </div>

            {/* Sort */}
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                Sort
              </h3>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={sb}
                  onChange={(e) => setSb(e.target.value as SortBy)}
                  className={selectClass}
                >
                  <option value="">Default</option>
                  <option value="publication_count">Publications</option>
                  <option value="citation_count">Citations</option>
                  <option value="h_index">h-index</option>
                  <option value="last_crawled">Recently updated</option>
                </select>
                {sb && (
                  <select
                    value={so}
                    onChange={(e) => setSo(e.target.value)}
                    className={selectClass}
                  >
                    <option value="desc">Descending</option>
                    <option value="asc">Ascending</option>
                  </select>
                )}
              </div>
            </div>

            {/* Metrics */}
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                Minimum metrics
              </h3>
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                  <label className="text-sm text-muted whitespace-nowrap">Publications</label>
                  <input
                    type="number"
                    min={0}
                    value={mp}
                    onChange={(e) => setMp(e.target.value)}
                    className={metricInputClass}
                    aria-label="Min publications"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label className="text-sm text-muted whitespace-nowrap">Citations</label>
                  <input
                    type="number"
                    min={0}
                    value={mc}
                    onChange={(e) => setMc(e.target.value)}
                    className={metricInputClass}
                    aria-label="Min citations"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label className="text-sm text-muted whitespace-nowrap">h-index</label>
                  <input
                    type="number"
                    min={0}
                    value={mh}
                    onChange={(e) => setMh(e.target.value)}
                    className={metricInputClass}
                    aria-label="Min h-index"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
