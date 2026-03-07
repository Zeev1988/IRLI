import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchLab } from "@/lib/api";
import { LabDetail } from "@/components/LabDetail";

interface PageProps {
  params: Promise<{ id: string }>;
}

function ArrowLeft() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 19-7-7 7-7" />
      <path d="M19 12H5" />
    </svg>
  );
}

export default async function LabPage({ params }: PageProps) {
  const { id } = await params;
  const labId = parseInt(id, 10);
  if (isNaN(labId)) notFound();

  const lab = await fetchLab(labId);
  if (!lab) notFound();

  return (
    <div className="space-y-6">
      <Link
        href="/"
        className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-navy shadow-soft transition-colors hover:border-accent/30 hover:bg-slate-50"
      >
        <ArrowLeft />
        Back to search
      </Link>
      <LabDetail lab={lab} />
    </div>
  );
}
