import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Leaf, ChevronRight, Loader2 } from "lucide-react";

interface Subspecies {
  taxon_id: string;
  taxon_full: string;
  subspecies: string;
  common_name: string;
  species_scientific_name: string;
}

interface SubspeciesResponse {
  taxon_id: string;
  species_scientific_name: string;
  subspecies_count: number;
  subspecies: Subspecies[];
}

interface SubspeciesSectionProps {
  taxonId: string;
}

export function SubspeciesSection({ taxonId }: SubspeciesSectionProps) {
  const router = useRouter();
  const [data, setData] = useState<SubspeciesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSubspecies = async () => {
      try {
        setIsLoading(true);
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth';
        const response = await fetch(
          `${API_URL}/species/${taxonId}/subspecies`
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch subspecies: ${response.status}`);
        }

        const result = await response.json();
        setData(result);
      } catch (err) {
        console.error("Error fetching subspecies:", err);
        setError(err instanceof Error ? err.message : "Failed to load subspecies");
      } finally {
        setIsLoading(false);
      }
    };

    fetchSubspecies();
  }, [taxonId]);

  // Don't render anything if loading
  if (isLoading) {
    return (
      <div className="p-4 rounded-lg bg-black/30 backdrop-blur-md border border-white/10">
        <div className="flex items-center justify-center py-4">
          <Loader2 className="w-5 h-5 animate-spin text-emerald-300 mr-2" />
          <span className="text-white/70">Loading subspecies...</span>
        </div>
      </div>
    );
  }

  // Don't render section if there's an error or no subspecies
  if (error || !data || data.subspecies_count === 0) {
    return null;
  }

  const handleSubspeciesClick = (subspeciesTaxonId: string) => {
    router.push(`/species/${subspeciesTaxonId}`);
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4 flex items-center">
        <Leaf className="w-5 h-5 mr-2 text-green-400" />
        Subspecies & Varieties
        <span className="ml-2 text-sm text-white/60 font-normal">
          ({data.subspecies_count})
        </span>
      </h2>
      <div className="p-4 rounded-lg bg-black/30 backdrop-blur-md border border-white/10">
        <p className="text-white/70 text-sm mb-3">
          This species has {data.subspecies_count} recognized{" "}
          {data.subspecies_count === 1 ? "subspecies" : "subspecies and varieties"}:
        </p>
        <div className="space-y-2">
          {data.subspecies.map((subspecies) => (
            <button
              key={subspecies.taxon_id}
              onClick={() => handleSubspeciesClick(subspecies.taxon_id)}
              className="w-full p-3 rounded-lg bg-black/40 hover:bg-black/60 border border-white/10 hover:border-emerald-400/50 transition-all group text-left"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="font-medium italic text-white group-hover:text-emerald-300 transition-colors">
                    {subspecies.taxon_full}
                  </div>
                  {subspecies.common_name && (
                    <div className="text-sm text-white/60 mt-1">
                      {subspecies.common_name.split(";")[0].trim() || "No common name"}
                    </div>
                  )}
                </div>
                <ChevronRight className="w-5 h-5 text-white/40 group-hover:text-emerald-300 transition-colors flex-shrink-0 ml-2" />
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
