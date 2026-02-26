"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Search, TreePine, Brain, Globe, Leaf, ArrowRight } from "lucide-react";
import { searchEcoregions, EcoregionSearchResult } from "@/lib/api";
import { useTour } from "@/context/tour-context";

export default function GuidePage() {
  const router = useRouter();
  const { autoStartTour } = useTour();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<EcoregionSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.length < 2) {
      setResults([]);
      setShowDropdown(false);
      return;
    }

    setIsSearching(true);
    debounceRef.current = setTimeout(async () => {
      const data = await searchEcoregions(query);
      setResults(data);
      setShowDropdown(true); // Show dropdown even for empty results (shows empty state)
      setIsSearching(false);
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  useEffect(() => {
    autoStartTour('guide');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <section className="relative w-full min-h-[calc(100vh-80px)] flex flex-col items-center justify-center">
      <div className="container relative z-10 px-4 md:px-6 mx-auto">
        <div className="flex flex-col items-center justify-center space-y-8 text-center">
          {/* Title */}
          <div className="flex flex-col items-center space-y-2" data-tour="guide-header">
            <h1 className="text-4xl font-bold tracking-tighter">
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-emerald-300 via-green-200 to-teal-300">
                Ecoregion Reforestation Guides
              </span>
            </h1>
            <p className="text-white/70 max-w-xl text-lg">
              Search 847 One Earth ecoregions to find LEAF-ranked species recommendations and AI-synthesized planting strategies.
            </p>
          </div>

          {/* Search */}
          <div className="w-full max-w-2xl relative" ref={dropdownRef} data-tour="guide-search">
            <div className="relative">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => results.length > 0 && setShowDropdown(true)}
                placeholder="Search ecoregions (e.g. Tyrrhenian, Appalachian, Borneo...)"
                className="w-full px-6 py-4 rounded-xl bg-black/30 backdrop-blur-md border-2 border-emerald-500/30 text-silvi-mint placeholder-silvi-mint/70 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-400/50 outline-none shadow-[0_0_15px_rgba(52,211,153,0.15)] transition-all duration-300 hover:border-emerald-400/40 hover:shadow-[0_0_20px_rgba(52,211,153,0.25)]"
              />
              <button
                type="button"
                className="absolute right-4 top-1/2 -translate-y-1/2 p-2 rounded-full hover:bg-emerald-500/20 transition-colors"
              >
                <Search className={`w-6 h-6 ${isSearching ? 'text-emerald-300 animate-pulse' : 'text-emerald-400/80 hover:text-emerald-300'}`} />
              </button>
            </div>

            {/* Dropdown */}
            {showDropdown && (
              <div className="absolute top-full mt-1 w-full bg-black/30 backdrop-blur-md rounded-xl shadow-lg max-h-96 overflow-auto z-20 border border-white/20">
                {results.length > 0 ? (
                  results.map((eco) => (
                    <button
                      key={eco.eco_id}
                      onClick={() => router.push(`/guide/${eco.eco_id}`)}
                      className="w-full p-4 text-left hover:bg-black/40 border-b border-white/10 last:border-b-0 transition-colors group"
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-medium text-white group-hover:text-emerald-300 transition-colors">{eco.eco_name}</div>
                        <ArrowRight className="h-5 w-5 text-white/0 group-hover:text-emerald-300 transition-all" />
                      </div>
                      <div className="text-sm text-white/60 flex gap-3 mt-1">
                        <span>{eco.biome_name}</span>
                        <span className="text-white/30">|</span>
                        <span>{eco.realm}</span>
                        <span className="text-white/30">|</span>
                        <span>{eco.area_km2.toLocaleString()} km²</span>
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="flex flex-col items-center justify-center p-8">
                    <Leaf className="w-6 h-6 text-emerald-300/50 mb-2" />
                    <span className="text-white/70">No matching ecoregions found</span>
                    <span className="text-xs text-white/50 mt-1">Try a different search term</span>
                  </div>
                )}
              </div>
            )}

            {query.length >= 1 && query.length < 2 && (
              <p className="text-xs text-white/70 text-center mt-2">
                Type at least 2 characters to search
              </p>
            )}
          </div>

          {/* Info Cards */}
          <div data-tour="guide-info-cards" className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-12 max-w-4xl w-full">
            <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-6 text-left">
              <TreePine className="h-8 w-8 text-emerald-400 mb-3" />
              <h3 className="text-lg font-semibold text-emerald-300 mb-1">LEAF Scoring</h3>
              <p className="text-sm text-white/70">
                Species ranked by Location-based Ecological Aptness Forecast using GBIF occurrences and WCVP native status.
              </p>
            </div>
            <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-6 text-left">
              <Brain className="h-8 w-8 text-emerald-400 mb-3" />
              <h3 className="text-lg font-semibold text-emerald-300 mb-1">AI Research</h3>
              <p className="text-sm text-white/70">
                Each guide can be enriched with AI-synthesized planting strategies and conservation context.
              </p>
            </div>
            <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-6 text-left">
              <Globe className="h-8 w-8 text-emerald-400 mb-3" />
              <h3 className="text-lg font-semibold text-emerald-300 mb-1">847 Ecoregions</h3>
              <p className="text-sm text-white/70">
                Full coverage of One Earth terrestrial ecoregions with biome and realm classification.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
