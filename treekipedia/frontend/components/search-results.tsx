"use client";

import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { searchTreeSpecies } from "@/lib/api";
import Link from "next/link";
import { Loader2 } from "lucide-react";

export function SearchResults() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q");

  const { data: results = [], isLoading } = useQuery({
    queryKey: ["trees", query],
    queryFn: () => searchTreeSpecies(query || ""),
    enabled: !!query,
  });

  if (!query) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center p-8 rounded-xl bg-black/20 backdrop-blur-md border border-white/10">
          <h3 className="text-lg font-semibold text-green-300 mb-2">
            Start Your Tree Research
          </h3>
          <p className="text-white/80">
            Enter a tree species name in the search box above to discover
            detailed information about different trees.
          </p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center flex-col gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-green-300" />
        <p className="text-white/80 p-4 rounded-xl">Searching for tree species...</p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center p-8 rounded-xl bg-white/10 backdrop-blur-md border border-white/20">
          <h3 className="text-lg font-semibold text-white mb-2">
            No Results Found
          </h3>
          <p className="text-white/70">
            We couldn&apos;t find any tree species matching "{query}". Try
            searching with a different name or check your spelling.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {results.map((tree) => (
          <Link
            key={tree.taxon_id}
            href={`/species/${tree.taxon_id}`}
            className="bg-black/30 backdrop-blur-md border border-white/20 p-6 rounded-xl text-white hover:bg-black/40 transition-all duration-300"
          >
            <h2 className="text-xl font-semibold">
              {tree.common_name}
            </h2>
            <p className="text-white/70 italic">
              {tree.accepted_scientific_name || tree.species_scientific_name || tree.species}
            </p>
            <ul className="mt-4 space-y-2 text-sm">
              <li className="flex justify-between items-center p-2 rounded-lg bg-black/30 border border-white/10">
                <span className="font-medium">Family:</span>
                <span>{tree.family}</span>
              </li>
              <li className="flex justify-between items-center p-2 rounded-lg bg-black/30 border border-white/10">
                <span className="font-medium">Genus:</span>
                <span>{tree.genus}</span>
              </li>
              {tree.subspecies && (
                <li className="flex justify-between items-center p-2 rounded-lg bg-black/30 border border-white/10">
                  <span className="font-medium">Subspecies:</span>
                  <span>{tree.subspecies}</span>
                </li>
              )}
              <li className="flex justify-between items-center p-2 rounded-lg bg-black/30 border border-white/10">
                <span className="font-medium">Class:</span>
                <span>{tree.taxonomic_class}</span>
              </li>
              <li className="flex justify-between items-center p-2 rounded-lg bg-black/30 border border-white/10">
                <span className="font-medium">Order:</span>
                <span>{tree.taxonomic_order}</span>
              </li>
            </ul>
          </Link>
        ))}
      </div>
    </div>
  );
}