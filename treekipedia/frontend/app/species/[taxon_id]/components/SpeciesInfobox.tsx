import React, { useState } from "react";
import { TreeSpecies } from "@/lib/types";
import {
  parseSemicolonList,
  parseNumericRange,
  formatRange,
  truncateList,
  parseKoppenCodes,
  isDataAvailable
} from "@/utils/speciesDataHelpers";

interface SpeciesInfoboxProps {
  species: TreeSpecies;
}

export function SpeciesInfobox({ species }: SpeciesInfoboxProps) {
  const [showAllClimate, setShowAllClimate] = useState(false);
  const [showAllBiomes, setShowAllBiomes] = useState(false);
  const [showAllCountries, setShowAllCountries] = useState(false);

  // Parse climate zones
  const climateZones = parseKoppenCodes(species.climate_type_koppengeiger);
  const { visible: visibleClimate, remaining: remainingClimate } = truncateList(climateZones, 4);

  // Parse precipitation
  const precipitation = parseNumericRange(species.annual_precipitation_mm);

  // Get derived habitat biomes from occurrence data
  const habitatBiomes = species.derived_biomes || [];
  const visibleBiomes = showAllBiomes ? habitatBiomes : habitatBiomes.slice(0, 3);
  const remainingBiomes = habitatBiomes.length - 3;

  // Parse native regions (using WCVP data)
  const countries = parseSemicolonList(species.wcvp_native);
  const { visible: visibleCountries, remaining: remainingCountries } = truncateList(countries, 4);

  // Check if we have any data to display
  const hasData = climateZones.length > 0 || precipitation || habitatBiomes.length > 0 || countries.length > 0;

  if (!hasData) {
    return null; // Don't show infobox if no data
  }

  return (
    <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-900/20 to-green-900/20 border border-emerald-500/20 backdrop-blur-sm">
      <h3 className="text-lg font-semibold mb-4 text-emerald-300">Quick Facts</h3>

      <div className="space-y-4">
        {/* Climate Zones */}
        {climateZones.length > 0 && (
          <div>
            <p className="text-sm text-white/60 mb-2">Climate Zones</p>
            <div className="flex flex-wrap gap-2">
              {(showAllClimate ? climateZones : visibleClimate).map((zone, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                  title={zone.description}
                >
                  {zone.description}
                </span>
              ))}
              {!showAllClimate && remainingClimate > 0 && (
                <button
                  onClick={() => setShowAllClimate(true)}
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                >
                  +{remainingClimate} more
                </button>
              )}
              {showAllClimate && climateZones.length > 4 && (
                <button
                  onClick={() => setShowAllClimate(false)}
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                >
                  Show less
                </button>
              )}
            </div>
          </div>
        )}

        {/* Annual Precipitation */}
        {precipitation && (
          <div>
            <p className="text-sm text-white/60 mb-1">Annual Rainfall</p>
            <p className="text-base text-white/85 font-medium">
              {formatRange(precipitation.min, precipitation.max, 'mm')}
            </p>
          </div>
        )}

        {/* Habitat Biomes (derived from occurrence data) */}
        {habitatBiomes.length > 0 && (
          <div>
            <p className="text-sm text-white/60 mb-2">Habitat Biomes</p>
            <div className="flex flex-wrap gap-2">
              {visibleBiomes.map((biome, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-600/20 text-green-300 border border-green-600/30"
                  title={`${biome.occurrences.toLocaleString()} occurrences in ${biome.tiles.toLocaleString()} tiles`}
                >
                  {biome.biome}
                </span>
              ))}
              {!showAllBiomes && remainingBiomes > 0 && (
                <button
                  onClick={() => setShowAllBiomes(true)}
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-600/10 text-green-400 border border-green-600/20 hover:bg-green-600/20 transition-colors"
                >
                  +{remainingBiomes} more
                </button>
              )}
              {showAllBiomes && habitatBiomes.length > 3 && (
                <button
                  onClick={() => setShowAllBiomes(false)}
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-600/10 text-green-400 border border-green-600/20 hover:bg-green-600/20 transition-colors"
                >
                  Show less
                </button>
              )}
            </div>
          </div>
        )}

        {/* Native Countries */}
        {countries.length > 0 && (
          <div>
            <p className="text-sm text-white/60 mb-2">Native to</p>
            <div className="flex flex-wrap gap-2">
              {(showAllCountries ? countries : visibleCountries).map((country, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30"
                >
                  {country}
                </span>
              ))}
              {!showAllCountries && remainingCountries > 0 && (
                <button
                  onClick={() => setShowAllCountries(true)}
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-colors"
                >
                  +{remainingCountries} more
                </button>
              )}
              {showAllCountries && countries.length > 4 && (
                <button
                  onClick={() => setShowAllCountries(false)}
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-colors"
                >
                  Show less
                </button>
              )}
            </div>
          </div>
        )}

        {/* Conservation Status */}
        {isDataAvailable(species.conservation_status_human) && (
          <div>
            <p className="text-sm text-white/60 mb-1">Conservation Status</p>
            <p className="text-base text-white/85 font-medium">
              {species.conservation_status_human}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
