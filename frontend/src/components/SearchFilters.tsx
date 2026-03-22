"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { UNIVERSITIES, UNIVERSITY_NAMES } from "@/lib/universities";
import { fetchTopics } from "@/lib/api";

const DEBOUNCE_MS = 400;

type SortBy = "publication_count" | "citation_count" | "h_index" | "last_crawled" | "";

function XIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="10"
      height="10"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}

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
  const q = searchParams.get("q") ?? "";
  const institution = searchParams.get("institution") ?? "";
  const faculty = searchParams.get("faculty") ?? "";
  const keyword = searchParams.get("keyword") ?? "";
  const topicsParam = searchParams.get("topics") ?? "";
  const topicsFromUrl = topicsParam ? topicsParam.split(",").map((t) => t.trim()).filter(Boolean) : [];
  const sortBy = (searchParams.get("sort_by") as SortBy) ?? "";
  const sortOrder = searchParams.get("sort_order") ?? "desc";
  const minPub = searchParams.get("min_publication_count") ?? "";
  const minCit = searchParams.get("min_citation_count") ?? "";
  const minH = searchParams.get("min_h_index") ?? "";

  const [expanded, setExpanded] = useState(false);
  const [topicsList, setTopicsList] = useState<string[]>([]);
  const [topicSearch, setTopicSearch] = useState("");
  const [inst, setInst] = useState(institution);
  const [fac, setFac] = useState(faculty);
  const [kw, setKw] = useState(keyword);
  const [selTopics, setSelTopics] = useState<string[]>(topicsFromUrl);
  const [sb, setSb] = useState(sortBy);
  const [so, setSo] = useState(sortOrder);
  const [mp, setMp] = useState(minPub);
  const [mc, setMc] = useState(minCit);
  const [mh, setMh] = useState(minH);
  const isSyncing = useRef(false);

  const activeCount = [
    q.trim(),
    inst,
    fac,
    kw,
    selTopics.length,
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
    setSelTopics(topicsFromUrl);
    setSb(sortBy);
    setSo(sortOrder);
    setMp(minPub);
    setMc(minCit);
    setMh(minH);
  }, [institution, faculty, keyword, topicsParam, sortBy, sortOrder, minPub, minCit, minH]);

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
        selTopics.join(",") !== topicsFromUrl.join(",") ||
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
          topics: selTopics.length ? selTopics.join(",") : undefined,
          sort_by: sb || undefined,
          sort_order: so,
          min_publication_count: minPubNum,
          min_citation_count: minCitNum,
          min_h_index: minHNum,
        });
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [inst, fac, kw, selTopics, sb, so, mp, mc, mh]);

  const handleInstitutionChange = (value: string) => {
    updateUrl({ institution: value, faculty: "" });
  };

  const handleFacultyChange = (value: string) => {
    updateUrl({ institution: inst, faculty: value });
  };

  const clearFilter = useCallback(
    (filter: string, value?: string) => {
      switch (filter) {
        case "query":
          updateUrl({ q: undefined });
          break;
        case "institution":
          updateUrl({ institution: undefined, faculty: undefined });
          break;
        case "faculty":
          updateUrl({ faculty: undefined });
          break;
        case "keyword":
          updateUrl({ keyword: undefined });
          break;
        case "topic":
          if (value)
            updateUrl({ topics: selTopics.filter((t) => t !== value).join(",") || undefined });
          break;
        case "sort":
          updateUrl({ sort_by: undefined, sort_order: undefined });
          break;
        case "min_pub":
          updateUrl({ min_publication_count: undefined });
          break;
        case "min_cit":
          updateUrl({ min_citation_count: undefined });
          break;
        case "min_h":
          updateUrl({ min_h_index: undefined });
          break;
      }
    },
    [updateUrl, selTopics]
  );

  const faculties = inst ? (UNIVERSITIES[inst] ?? []) : [];

  useEffect(() => {
    fetchTopics().then(setTopicsList).catch(() => setTopicsList([]));
  }, []);

  const toggleTopic = (t: string) => {
    setSelTopics((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  };

  const topicSearchLower = topicSearch.trim().toLowerCase();
  const filteredTopics = topicSearchLower
    ? topicsList.filter((t) => t.toLowerCase().includes(topicSearchLower))
    : topicsList;
  const selectedNotInFilter = selTopics.filter((t) => !filteredTopics.includes(t));
  const topicsToShow = [
    ...selectedNotInFilter,
    ...filteredTopics.filter((t) => !selectedNotInFilter.includes(t)),
  ];

  const selectClass =
    "rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-navy shadow-soft focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";
  const inputClass =
    "rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-navy shadow-soft placeholder-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";
  const metricInputClass =
    "w-16 rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm text-navy shadow-soft focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

  const filterPills = [
    ...(q.trim() ? [{ key: "query", label: "query", value: q.trim() }] : []),
    ...(inst ? [{ key: "institution", label: "institution", value: inst }] : []),
    ...(fac ? [{ key: "faculty", label: "faculty", value: fac }] : []),
    ...(kw ? [{ key: "keyword", label: "keyword", value: kw }] : []),
    ...selTopics.map((t) => ({ key: `topic-${t}`, label: "topic", value: t })),
    ...(sb
      ? [
          {
            key: "sort",
            label: "sort",
            value: ({ publication_count: "pubs", citation_count: "cites", h_index: "h", last_crawled: "recent" }[sb] ?? sb) + (so === "asc" ? " ↑" : " ↓"),
          },
        ]
      : []),
    ...(mp ? [{ key: "min_pub", label: "min pubs", value: mp }] : []),
    ...(mc ? [{ key: "min_cit", label: "min cites", value: mc }] : []),
    ...(mh ? [{ key: "min_h", label: "min h", value: mh }] : []),
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white/80 p-4 shadow-soft">
      <div
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((e) => !e)}
        onKeyDown={(e) => e.key === "Enter" && setExpanded((x) => !x)}
        className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-navy hover:bg-slate-50 transition-colors"
        aria-expanded={expanded}
      >
        <span className="flex flex-wrap items-center gap-2">
          Filters {activeCount > 0 && `(${activeCount})`}
          {filterPills.map(({ key, label, value }) => (
            <span
              key={key}
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 rounded-full bg-accent/15 pl-2 pr-1 py-0.5 text-xs font-medium text-accent"
            >
              {label}: {value}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  clearFilter(key.startsWith("topic-") ? "topic" : key, key.startsWith("topic-") ? value : undefined);
                }}
                className="rounded-full p-0.5 hover:bg-accent/25 transition-colors"
                aria-label={`Remove ${label} filter`}
              >
                <XIcon />
              </button>
            </span>
          ))}
        </span>
        <ChevronDown open={expanded} />
      </div>
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

            {/* Topics */}
            {topicsList.length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                  Topics
                </h3>
                <input
                  type="text"
                  placeholder="Search topics..."
                  value={topicSearch}
                  onChange={(e) => setTopicSearch(e.target.value)}
                  className={`${inputClass} mb-2 w-full`}
                  aria-label="Search topics"
                />
                <div className="max-h-40 overflow-y-auto rounded-lg border border-slate-200 bg-white p-2">
                  {topicsToShow.map((t) => (
                    <label
                      key={t}
                      className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-slate-50"
                    >
                      <input
                        type="checkbox"
                        checked={selTopics.includes(t)}
                        onChange={() => toggleTopic(t)}
                        className="rounded border-slate-300 text-accent focus:ring-accent/20"
                      />
                      {t}
                    </label>
                  ))}
                </div>
              </div>
            )}

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
