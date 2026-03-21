import type { Lab } from "@/lib/api";

interface LabDetailProps {
  lab: Lab;
}

function ExternalLinkIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" x2="21" y1="14" y2="3" />
    </svg>
  );
}

export function LabDetail({ lab }: LabDetailProps) {
  const isHiring =
    lab.hiring_status === "true" ||
    lab.hiring_status.toLowerCase().includes("hiring") ||
    lab.hiring_status.toLowerCase().includes("looking");

  const hasMetrics =
    lab.publication_count != null ||
    lab.citation_count != null ||
    lab.h_index != null;

  const Section = ({
    title,
    children,
  }: {
    title: string;
    children: React.ReactNode;
  }) => (
    <section className="rounded-xl border border-slate-200 bg-slate-50/50 p-5 shadow-soft">
      <h2 className="font-serif text-lg font-medium text-navy">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );

  const LinkButton = ({
    href,
    children,
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 rounded-lg border border-accent/30 bg-accent/5 px-4 py-2.5 text-sm font-medium text-accent transition-colors hover:bg-accent/10"
    >
      {children}
      <ExternalLinkIcon />
    </a>
  );

  return (
    <article className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-serif text-2xl font-semibold text-navy">
              {lab.pi_name}
            </h1>
            <p className="mt-1 text-muted">
              {lab.institution} · {lab.faculty}
            </p>
          </div>
          {isHiring && (
            <span className="rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-700">
              Hiring
            </span>
          )}
        </div>

        {hasMetrics && (
          <div className="mt-6 flex flex-wrap gap-6">
            {lab.publication_count != null && (
              <div className="rounded-lg bg-slate-100 px-4 py-2">
                <span className="text-2xl font-semibold text-navy">
                  {lab.publication_count}
                </span>
                <span className="ml-2 text-sm text-muted">papers</span>
              </div>
            )}
            {lab.citation_count != null && (
              <div className="rounded-lg bg-slate-100 px-4 py-2">
                <span className="text-2xl font-semibold text-navy">
                  {lab.citation_count >= 1000
                    ? `${(lab.citation_count / 1000).toFixed(1)}k`
                    : lab.citation_count}
                </span>
                <span className="ml-2 text-sm text-muted">citations</span>
              </div>
            )}
            {lab.h_index != null && (
              <div className="rounded-lg bg-slate-100 px-4 py-2">
                <span className="text-2xl font-semibold text-navy">
                  {lab.h_index}
                </span>
                <span className="ml-2 text-sm text-muted">h-index</span>
              </div>
            )}
          </div>
        )}
      </div>

      {lab.research_summary?.length > 0 && (
        <Section title="Research Summary">
          <ul className="list-inside list-disc space-y-1.5 text-slate-600">
            {lab.research_summary.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </Section>
      )}

      {lab.keywords?.length > 0 && (
        <Section title="Keywords">
          <div className="flex flex-wrap gap-2">
            {lab.keywords.map((k) => (
              <span
                key={k}
                className="rounded-lg bg-slate-200/80 px-2.5 py-1 text-sm text-slate-700"
              >
                {k}
              </span>
            ))}
          </div>
        </Section>
      )}

      {lab.technologies?.length > 0 && (
        <Section title="Technologies">
          <div className="flex flex-wrap gap-2">
            {lab.technologies.map((t) => (
              <span
                key={t}
                className="rounded-lg bg-accent/10 px-2.5 py-1 text-sm text-accent"
              >
                {t}
              </span>
            ))}
          </div>
        </Section>
      )}

      <div className="flex flex-wrap gap-3">
        {lab.semantic_scholar_author_id && (
          <LinkButton
            href={`https://openalex.org/${lab.semantic_scholar_author_id}`}
          >
            View on OpenAlex
          </LinkButton>
        )}
        {lab.lab_url && (
          <LinkButton href={lab.lab_url}>Visit lab website</LinkButton>
        )}
      </div>
    </article>
  );
}
