import Link from "next/link";
import type { Lab } from "@/lib/api";

interface LabCardProps {
  lab: Lab;
}

export function LabCard({ lab }: LabCardProps) {
  const isHiring =
    lab.hiring_status === "true" ||
    lab.hiring_status.toLowerCase().includes("hiring") ||
    lab.hiring_status.toLowerCase().includes("looking");

  const hasMetrics =
    lab.publication_count != null ||
    lab.citation_count != null ||
    lab.h_index != null;

  const formatCitations = (n: number) =>
    n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

  return (
    <Link
      href={`/labs/${lab.id}`}
      className="block rounded-xl border border-slate-200 bg-white p-6 shadow-md transition-all duration-300 hover:-translate-y-0.5 hover:border-accent/30 hover:shadow-soft-lg"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className="font-serif text-lg font-semibold text-navy">
          {lab.pi_name}
        </h2>
        {isHiring && (
          <span className="shrink-0 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
            Hiring
          </span>
        )}
      </div>
      <p className="mt-1 text-sm text-muted">
        {lab.institution} · {lab.faculty}
      </p>
      {hasMetrics && (
        <p className="mt-2 text-xs text-slate-500">
          {lab.publication_count != null && `${lab.publication_count} papers`}
          {lab.publication_count != null && lab.citation_count != null && " · "}
          {lab.citation_count != null &&
            `${formatCitations(lab.citation_count)} citations`}
          {lab.h_index != null &&
            (lab.publication_count != null || lab.citation_count != null
              ? " · "
              : "") + `h=${lab.h_index}`}
        </p>
      )}
      {lab.research_summary?.length > 0 && (
        <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-slate-600">
          {lab.research_summary[0]}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-1.5">
        {lab.keywords?.slice(0, 4).map((k) => (
          <span
            key={k}
            className="rounded-lg bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
          >
            {k}
          </span>
        ))}
        {lab.technologies?.slice(0, 2).map((t) => (
          <span
            key={t}
            className="rounded-lg bg-accent/10 px-2 py-0.5 text-xs text-accent"
          >
            {t}
          </span>
        ))}
      </div>
    </Link>
  );
}
