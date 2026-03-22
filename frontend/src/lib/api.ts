// Set NEXT_PUBLIC_API_URL in Vercel/env (e.g. https://api.your-app.com). Defaults to localhost for dev.
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Lab {
  id: number;
  pi_name: string;
  institution: string;
  faculty: string;
  research_summary: string[];
  keywords: string[];
  technologies: string[];
  hiring_status: string;
  lab_url: string;
  last_crawled_at: string | null;
  publication_count: number | null;
  citation_count: number | null;
  h_index: number | null;
  metrics_updated_at: string | null;
  semantic_scholar_author_id: string | null;
}

export interface LabFilters {
  q?: string;
  institution?: string;
  faculty?: string;
  keyword?: string;
  topic?: string[];
  min_publication_count?: number;
  min_citation_count?: number;
  min_h_index?: number;
  sort_by?: "publication_count" | "citation_count" | "h_index" | "last_crawled";
  sort_order?: "asc" | "desc";
  limit?: number;
}

export async function fetchLabs(
  filters: LabFilters = {},
  limit = 20
): Promise<Lab[]> {
  const params = new URLSearchParams();
  if (filters.q?.trim()) params.set("q", filters.q.trim());
  if (filters.institution) params.set("institution", filters.institution);
  if (filters.faculty) params.set("faculty", filters.faculty);
  if (filters.keyword) params.set("keyword", filters.keyword);
  (filters.topic ?? []).forEach((t) => params.append("topic", t));
  if (filters.min_publication_count != null) params.set("min_publication_count", String(filters.min_publication_count));
  if (filters.min_citation_count != null) params.set("min_citation_count", String(filters.min_citation_count));
  if (filters.min_h_index != null) params.set("min_h_index", String(filters.min_h_index));
  if (filters.sort_by) params.set("sort_by", filters.sort_by);
  if (filters.sort_order) params.set("sort_order", filters.sort_order);
  params.set("limit", String(filters.limit ?? limit));
  const res = await fetch(`${API_BASE}/api/v1/labs?${params}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`Failed to fetch labs (${res.status}): ${msg}`);
  }
  return res.json();
}

export async function fetchTopics(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/v1/labs/topics`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch topics (${res.status})`);
  return res.json();
}

export async function fetchLab(id: number): Promise<Lab | null> {
  const res = await fetch(`${API_BASE}/api/v1/labs/${id}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch lab");
  return res.json();
}
