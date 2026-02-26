"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { getEcoregionGuide, EcoregionGuideResponse, EcoregionGuideSpecies } from "@/lib/api";
import Link from "next/link";
import { useTour } from "@/context/tour-context";

function Accordion({ id, title, defaultOpen = false, children, badge }: {
  id?: string;
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  badge?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div id={id} className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 overflow-hidden scroll-mt-4">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-black/20 transition-colors"
      >
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          {badge && (
            <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-500/30">
              {badge}
            </span>
          )}
        </div>
        {open ? <ChevronUp className="h-5 w-5 text-white/50" /> : <ChevronDown className="h-5 w-5 text-white/50" />}
      </button>
      {open && <div className="px-6 py-4 border-t border-white/10">{children}</div>}
    </div>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const colors: Record<string, string> = {
    BEST: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    GOOD: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    ACCEPTABLE: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    LOW: "bg-white/10 text-white/50 border-white/20",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${colors[tier] || colors.LOW}`}>
      {tier}
    </span>
  );
}

function SpeciesCard({ species, enriched = false }: { species: EcoregionGuideSpecies; enriched?: boolean }) {
  return (
    <Link
      href={`/species/${species.taxon_id}`}
      className="block rounded-xl bg-black/30 backdrop-blur-md border border-white/15 p-4 hover:border-emerald-500/50 hover:bg-black/40 transition-all group"
    >
      <div className="flex items-start justify-between mb-1">
        <h3 className="text-sm font-semibold text-white group-hover:text-emerald-300 transition-colors italic">
          {species.scientific_name || species.taxon_id}
        </h3>
        <TierBadge tier={species.tier} />
      </div>
      {(species.popular_common_name_ai || species.common_name) && (
        <p className="text-xs text-white/60 mb-2">
          {species.popular_common_name_ai && species.popular_common_name_ai !== 'NA'
            ? species.popular_common_name_ai
            : species.common_name?.split(';').find(n => n.trim()) || ''}
        </p>
      )}
      <div className="flex gap-2 text-xs text-white/50 mb-2">
        <span>Score: {species.leaf_score}</span>
        {species.is_native && <span className="text-emerald-400">Native</span>}
        {species.maximum_height_ai && species.maximum_height_ai !== 'NA' && <span>{species.maximum_height_ai}m</span>}
      </div>
      {enriched && species.general_description_ai && species.general_description_ai !== 'NA' && (
        <p className="text-xs text-white/60 line-clamp-2">{species.general_description_ai}</p>
      )}
    </Link>
  );
}

function CompactSpeciesRow({ species }: { species: EcoregionGuideSpecies }) {
  return (
    <Link
      href={`/species/${species.taxon_id}`}
      className="flex items-center justify-between px-3 py-2 hover:bg-black/30 rounded-lg transition-colors group"
    >
      <div className="flex-1 min-w-0">
        <span className="text-sm text-white group-hover:text-emerald-300 transition-colors italic truncate">
          {species.scientific_name || species.taxon_id}
        </span>
        {(species.popular_common_name_ai || species.common_name) && (
          <span className="text-xs text-white/50 ml-2">
            {species.popular_common_name_ai && species.popular_common_name_ai !== 'NA'
              ? species.popular_common_name_ai
              : species.common_name?.split(';').find(n => n.trim()) || ''}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2 ml-2 shrink-0">
        {species.is_native && <span className="text-xs text-emerald-400">N</span>}
        <span className="text-xs text-white/50">{species.leaf_score}</span>
        <TierBadge tier={species.tier} />
      </div>
    </Link>
  );
}

export default function EcoregionGuidePage() {
  const params = useParams();
  const router = useRouter();
  const ecoId = params.eco_id as string;
  const { autoStartTour } = useTour();
  const [guide, setGuide] = useState<EcoregionGuideResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading) {
      autoStartTour('guide_detail');
    }
  }, [loading]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await getEcoregionGuide(ecoId);
        setGuide(data);
      } catch (err) {
        setError("Failed to load ecoregion guide");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [ecoId]);

  if (loading) {
    return (
      <div className="min-h-screen">
        <div className="container mx-auto px-4 py-16 flex justify-center items-center">
          <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-8 w-full max-w-2xl">
            <div className="flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-emerald-300" />
              <span className="ml-3 text-white/70">Loading guide...</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !guide) {
    return (
      <div className="min-h-screen">
        <div className="container mx-auto px-4 py-16 flex justify-center items-center">
          <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-8 w-full max-w-2xl text-center">
            <p className="text-red-400 mb-4">{error || "Guide not found"}</p>
            <button
              onClick={() => router.push("/guide")}
              className="text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              Back to search
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { ecoregion, synthesized_content, statistics, top_species, species_by_tier, countries } = guide;
  const sc = synthesized_content;

  return (
    <div className="min-h-screen py-8">
      <div className="max-w-5xl mx-auto px-4">
        {/* Back button */}
        <button
          onClick={() => router.push("/guide")}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-black/40 backdrop-blur-md border border-white/15 text-white hover:bg-black/60 transition-colors mb-6"
        >
          <ArrowLeft className="h-4 w-4" /> Back to ecoregion search
        </button>

        {/* Header */}
        <div data-tour="ecoregion-header" className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-6 mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-white mb-3">{ecoregion.eco_name}</h1>
          <div className="flex flex-wrap gap-2 text-xs sm:text-sm">
            <span className="bg-black/30 backdrop-blur-md px-2 sm:px-3 py-1 rounded-full text-white/80 border border-white/10">{ecoregion.biome_name}</span>
            <span className="bg-black/30 backdrop-blur-md px-2 sm:px-3 py-1 rounded-full text-white/80 border border-white/10">{ecoregion.realm}</span>
            <span className="bg-black/30 backdrop-blur-md px-2 sm:px-3 py-1 rounded-full text-white/80 border border-white/10">{ecoregion.area_km2.toLocaleString()} km²</span>
            {countries.length > 0 && (
              <span className="bg-black/30 backdrop-blur-md px-2 sm:px-3 py-1 rounded-full text-white/80 border border-white/10">
                {countries.slice(0, 3).join(", ")}{countries.length > 3 ? ` +${countries.length - 3}` : ""}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-2 sm:gap-4 mt-4 text-xs sm:text-sm">
            <span className="text-emerald-400">{statistics.total_species.toLocaleString()} species scored</span>
            <span className="text-white/30 hidden sm:inline">|</span>
            <span className="text-white/60">{statistics.by_tier.BEST} Best · {statistics.by_tier.GOOD} Good · {statistics.by_tier.ACCEPTABLE} Acceptable</span>
          </div>

          {/* Quick Jump Links */}
          <div data-tour="quick-jump" className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-white/10">
            <span className="text-xs text-white/50 mr-1">Jump to:</span>
            <a href="#overview" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">Overview</a>
            <span className="text-white/20">·</span>
            <a href="#top-species" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">Top Species</a>
            <span className="text-white/20">·</span>
            <a href="#all-species" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">All Species</a>
            {sc?.planting_strategy && (
              <>
                <span className="text-white/20">·</span>
                <a href="#planting" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">Planting</a>
              </>
            )}
            {sc?.climate_context && (
              <>
                <span className="text-white/20">·</span>
                <a href="#climate" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">Climate</a>
              </>
            )}
            {sc?.conservation_notes && (
              <>
                <span className="text-white/20">·</span>
                <a href="#conservation" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">Conservation</a>
              </>
            )}
            <span className="text-white/20">·</span>
            <a href="#methodology" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">Methodology</a>
          </div>
        </div>

        {/* Accordion Sections */}
        <div className="space-y-3">
          {/* Overview */}
          <Accordion id="overview" title="Overview" defaultOpen={true} badge={sc ? "Synthesized" : undefined}>
            {sc?.overview_intro ? (
              <div className="prose prose-invert prose-sm max-w-none">
                {sc.overview_intro.split("\n").map((p, i) => <p key={i} className="text-white/80 mb-3">{p}</p>)}
              </div>
            ) : (
              <p className="text-white/50 italic">
                AI synthesis not yet generated for this ecoregion. The species data below is available based on LEAF scoring.
              </p>
            )}
          </Accordion>

          {/* Top Recommended Species */}
          <div data-tour="top-species">
          <Accordion id="top-species" title="Top Recommended Species" defaultOpen={true} badge={`${top_species.length} species`}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {top_species.map((sp) => (
                <SpeciesCard key={sp.taxon_id} species={sp} enriched={true} />
              ))}
            </div>
          </Accordion>
          </div>

          {/* All Species by Tier */}
          <div data-tour="all-species">
          <Accordion id="all-species" title="All Species by Tier" badge={`${statistics.total_species} total`}>
            {(["BEST", "GOOD", "ACCEPTABLE"] as const).map((tier) => {
              const tierSpecies = species_by_tier[tier];
              if (!tierSpecies || tierSpecies.length === 0) return null;
              return (
                <div key={tier} className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TierBadge tier={tier} />
                    <span className="text-sm text-white/60">{tierSpecies.length} species</span>
                  </div>
                  <div className="rounded-lg bg-black/20 backdrop-blur-md border border-white/10 divide-y divide-white/5">
                    {tierSpecies.slice(0, 50).map((sp) => (
                      <CompactSpeciesRow key={sp.taxon_id} species={sp} />
                    ))}
                    {tierSpecies.length > 50 && (
                      <div className="px-3 py-2 text-xs text-white/50">
                        + {tierSpecies.length - 50} more species
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </Accordion>
          </div>

          {/* Planting Strategy */}
          {sc?.planting_strategy && (
            <Accordion id="planting" title="Planting Strategy">
              <div className="prose prose-invert prose-sm max-w-none">
                {sc.planting_strategy.split("\n").map((p, i) => <p key={i} className="text-white/80 mb-3">{p}</p>)}
              </div>
            </Accordion>
          )}

          {/* Climate & Growing Conditions */}
          {sc?.climate_context && (
            <Accordion id="climate" title="Climate & Growing Conditions">
              <div className="prose prose-invert prose-sm max-w-none">
                {sc.climate_context.split("\n").map((p, i) => <p key={i} className="text-white/80 mb-3">{p}</p>)}
              </div>
            </Accordion>
          )}

          {/* Conservation Notes */}
          {sc?.conservation_notes && (
            <Accordion id="conservation" title="Conservation Notes">
              <div className="prose prose-invert prose-sm max-w-none">
                {sc.conservation_notes.split("\n").map((p, i) => <p key={i} className="text-white/80 mb-3">{p}</p>)}
              </div>
            </Accordion>
          )}

          {/* Methodology */}
          <Accordion id="methodology" title="Methodology">
            <div className="space-y-3 text-sm text-white/70">
              <p>
                <strong className="text-emerald-300">LEAF Score</strong> — Location-based Ecological Aptness Forecast.
                Species are ranked by weighted affinity calculated from GBIF occurrence data within the ecoregion,
                multiplied by a 2x native boost for species confirmed native via WCVP. Introduced species are excluded.
                Scores are percentile-normalized (0-100).
              </p>
              <p>
                <strong className="text-emerald-300">Tiers:</strong> BEST (≥90), GOOD (≥70), ACCEPTABLE (≥50), LOW (&lt;50)
              </p>
              <p>
                <strong className="text-emerald-300">Data Sources:</strong> GBIF occurrences via geohash tiles (6.46M tiles, 96.5M occurrences),
                WCVP native/introduced status, One Earth terrestrial ecoregions.
              </p>
              {sc && (
                <p>
                  <strong className="text-emerald-300">AI Synthesis:</strong> Generated by {sc.model_used || "Grok 4.1 Fast"} on{" "}
                  {new Date(sc.generated_at).toLocaleDateString()} (v{sc.synthesis_version}).
                  Based on top {sc.species_count} species with AI-researched ecological data.
                </p>
              )}
            </div>
          </Accordion>
        </div>
      </div>
    </div>
  );
}
