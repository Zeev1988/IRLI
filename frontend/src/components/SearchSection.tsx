"use client";

import { SearchBar } from "./SearchBar";
import { SearchFilters } from "./SearchFilters";

export function SearchSection() {
  return (
    <section className="rounded-2xl bg-gradient-to-b from-cream to-slate-50/50 px-6 py-8 md:py-10">
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="font-serif text-2xl font-semibold text-navy md:text-3xl">
            Discover graduate research labs across Israel
          </h2>
        </div>
        <SearchBar />
        <SearchFilters />
      </div>
    </section>
  );
}
