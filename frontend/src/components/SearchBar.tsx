"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const DEBOUNCE_MS = 300;

export function SearchBar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const [input, setInput] = useState(q);
  const isSyncingFromUrl = useRef(false);

  useEffect(() => {
    isSyncingFromUrl.current = true;
    setInput(q);
  }, [q]);

  const updateUrl = useCallback(
    (value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value.trim()) params.set("q", value.trim());
      else params.delete("q");
      router.push(`/?${params.toString()}`);
    },
    [router, searchParams]
  );

  useEffect(() => {
    if (isSyncingFromUrl.current) {
      isSyncingFromUrl.current = false;
      return;
    }
    const t = setTimeout(() => updateUrl(input), DEBOUNCE_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input]);

  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
      </span>
      <input
        type="search"
        placeholder="Search by name, topic, or institution..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && updateUrl(input)}
        className="w-full rounded-xl border border-slate-200 bg-white py-4 pl-12 pr-4 text-navy shadow-soft placeholder-muted transition-shadow focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 focus:shadow-soft-lg"
      />
    </div>
  );
}
