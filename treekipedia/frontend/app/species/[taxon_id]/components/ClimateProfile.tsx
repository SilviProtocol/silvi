import React, { useState } from "react";
import { TreeSpecies } from "@/lib/types";
import {
  parseNumericRange,
  formatRange,
  parseKoppenCodes,
  truncateList
} from "@/utils/speciesDataHelpers";
import { Cloud, Droplets, Thermometer } from "lucide-react";

interface ClimateProfileProps {
  species: TreeSpecies;
}

export function ClimateProfile({ species }: ClimateProfileProps) {
  const [showAllZones, setShowAllZones] = useState(false);

  // Parse all climate data
  const climateZones = parseKoppenCodes(species.climate_type_koppengeiger);
  const annualPrecip = parseNumericRange(species.annual_precipitation_mm);
  const tempRange = parseNumericRange(species.annual_temperature_range_c);
  const wettestMonth = parseNumericRange(species.wettest_month_precipitation_mm);
  const driestMonth = parseNumericRange(species.driest_month_precipitation_mm);

  const { visible: visibleZones, remaining: remainingZones } = truncateList(climateZones, 8);

  // Check if we have any climate data
  const hasData = climateZones.length > 0 || annualPrecip || tempRange;

  if (!hasData) {
    return null;
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-white flex items-center gap-2">
        <Cloud className="w-5 h-5 text-emerald-400" />
        Climate Profile
      </h3>

      {/* Köppen Climate Zones */}
      {climateZones.length > 0 && (
        <div className="p-4 rounded-xl bg-black/40 border border-white/15">
          <h4 className="font-medium text-white/60 mb-3">Climate Zones (Köppen-Geiger)</h4>
          <div className="flex flex-wrap gap-2">
            {(showAllZones ? climateZones : visibleZones).map((zone, idx) => (
              <span
                key={idx}
                className="inline-flex items-center px-3 py-1.5 rounded-full text-sm bg-emerald-500/20 text-emerald-200 border border-emerald-500/30"
                title={`${zone.code} - ${zone.description}`}
              >
                <span className="font-semibold mr-2">{zone.code}</span>
                <span className="text-emerald-300/80">{zone.description}</span>
              </span>
            ))}
            {!showAllZones && remainingZones > 0 && (
              <button
                onClick={() => setShowAllZones(true)}
                className="inline-flex items-center px-3 py-1.5 rounded-full text-sm bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
              >
                +{remainingZones} more zones
              </button>
            )}
            {showAllZones && climateZones.length > 8 && (
              <button
                onClick={() => setShowAllZones(false)}
                className="inline-flex items-center px-3 py-1.5 rounded-full text-sm bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
              >
                Show less
              </button>
            )}
          </div>
        </div>
      )}

      {/* Precipitation Data */}
      {(annualPrecip || wettestMonth || driestMonth) && (
        <div className="p-4 rounded-xl bg-black/40 border border-white/15">
          <h4 className="font-medium text-white/60 mb-3 flex items-center gap-2">
            <Droplets className="w-4 h-4 text-blue-400" />
            Precipitation
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {annualPrecip && (
              <div>
                <p className="text-sm text-white/60 mb-1">Annual</p>
                <p className="text-base text-white/85 font-medium">
                  {formatRange(annualPrecip.min, annualPrecip.max, 'mm')}
                </p>
              </div>
            )}
            {wettestMonth && (
              <div>
                <p className="text-sm text-white/60 mb-1">Wettest Month</p>
                <p className="text-base text-white/85 font-medium">
                  {formatRange(wettestMonth.min, wettestMonth.max, 'mm')}
                </p>
              </div>
            )}
            {driestMonth && (
              <div>
                <p className="text-sm text-white/60 mb-1">Driest Month</p>
                <p className="text-base text-white/85 font-medium">
                  {formatRange(driestMonth.min, driestMonth.max, 'mm')}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Temperature Data */}
      {tempRange && (
        <div className="p-4 rounded-xl bg-black/40 border border-white/15">
          <h4 className="font-medium text-white/60 mb-3 flex items-center gap-2">
            <Thermometer className="w-4 h-4 text-amber-400" />
            Temperature
          </h4>
          <div>
            <p className="text-sm text-white/60 mb-1">Annual Temperature Range</p>
            <p className="text-base text-white/85 font-medium">
              {formatRange(tempRange.min, tempRange.max, '°C', 1)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
