"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

const SORT_LABELS: Record<string, string> = {
  publication_count: "publications",
  citation_count: "citations",
  h_index: "h-index",
  last_crawled: "recently updated",
};

function XIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="12"
      height="12"
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

export function ActiveFilterPills() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const q = searchParams.get("q") ?? "";
  const institution = searchParams.get("institution") ?? "";
  const faculty = searchParams.get("faculty") ?? "";
  const keyword = searchParams.get("keyword") ?? "";
  const topicsParam = searchParams.get("topics") ?? "";
  const topics = topicsParam ? topicsParam.split(",").map((t) => t.trim()).filter(Boolean) : [];
  const sortBy = searchParams.get("sort_by") ?? "";
  const sortOrder = searchParams.get("sort_order") ?? "desc";
  const minPub = searchParams.get("min_publication_count") ?? "";
  const minCit = searchParams.get("min_citation_count") ?? "";
  const minH = searchParams.get("min_h_index") ?? "";

  const removeFilter = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [k, v] of Object.entries(updates)) {
        if (v === undefined || v === "") {
          params.delete(k);
        } else {
          params.set(k, v);
        }
      }
      router.push(`/?${params.toString()}`);
    },
    [router, searchParams]
  );

  const pills: { key: string; label: string; value: string }[] = [];
  if (q.trim()) pills.push({ key: "query", label: "query", value: q.trim() });
  if (institution.trim()) pills.push({ key: "institution", label: "institution", value: institution.trim() });
  if (faculty.trim()) pills.push({ key: "faculty", label: "faculty", value: faculty.trim() });
  if (keyword.trim()) pills.push({ key: "keyword", label: "keyword", value: keyword.trim() });
  topics.forEach((t) => pills.push({ key: `topic-${t}`, label: "topic", value: t }));
  if (sortBy) {
    pills.push({
      key: "sort",
      label: "sort",
      value: (SORT_LABELS[sortBy] ?? sortBy) + (sortOrder === "asc" ? " ↑" : " ↓"),
    });
  }
  if (minPub) pills.push({ key: "min_pub", label: "min pubs", value: minPub });
  if (minCit) pills.push({ key: "min_cit", label: "min citations", value: minCit });
  if (minH) pills.push({ key: "min_h", label: "min h-index", value: minH });

  if (pills.length === 0) return null;

  const handleRemove = (pill: (typeof pills)[0]) => {
    switch (pill.key) {
      case "query":
        removeFilter({ q: undefined });
        break;
      case "institution":
        removeFilter({ institution: undefined, faculty: undefined });
        break;
      case "faculty":
        removeFilter({ faculty: undefined });
        break;
      case "keyword":
        removeFilter({ keyword: undefined });
        break;
      case "sort":
        removeFilter({ sort_by: undefined, sort_order: undefined });
        break;
      case "min_pub":
        removeFilter({ min_publication_count: undefined });
        break;
      case "min_cit":
        removeFilter({ min_citation_count: undefined });
        break;
      case "min_h":
        removeFilter({ min_h_index: undefined });
        break;
      default:
        if (pill.key.startsWith("topic-")) {
          const topic = pill.value;
          const rest = topics.filter((x) => x !== topic);
          removeFilter({ topics: rest.length ? rest.join(",") : undefined });
        }
    }
  };

  return (
    <span className="inline-flex flex-wrap gap-1.5">
      {pills.map((pill) => (
        <span
          key={pill.key}
          className="inline-flex items-center gap-1 rounded-full bg-slate-100 pl-2 pr-1 py-0.5 text-xs text-muted"
        >
          <span className="font-medium text-navy">{pill.label}:</span> {pill.value}
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleRemove(pill);
            }}
            className="rounded-full p-0.5 hover:bg-slate-200 text-muted hover:text-navy transition-colors"
            aria-label={`Remove ${pill.label} filter`}
          >
            <XIcon />
          </button>
        </span>
      ))}
    </span>
  );
}
