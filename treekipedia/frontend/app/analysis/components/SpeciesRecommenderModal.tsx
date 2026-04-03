'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, Loader2, TreePine, Leaf, AlertTriangle, Globe, Sparkles, ChevronDown, ChevronUp, Target } from 'lucide-react';
import Link from 'next/link';

// ============================================================================
// Types
// ============================================================================

interface Strategy {
  key: string;
  name: string;
  description: string;
  weights: {
    spatial: number;
    abiotic: number;
    functional: number;
    ecosystem: number;
    biotic: number;
  };
}

interface SafeBComponents {
  spatial: number;
  abiotic: number;
  functional: number;
  ecosystem: number;
  biotic: number;
}

interface RadarScores {
  sinr_habitat: number | null;
  spatial: number;
  abiotic: number;
  functional: number;
  ecosystem: number;
  biotic: number;
}

interface SinrDetail {
  prob_native: number;
  prob_introduced: number;
  prob_best: number;
  rank: number;
}

interface Recommendation {
  rank: number;
  taxon_id: string;
  scientific_name: string;
  common_name: string | null;
  family: string;
  safeb_score: number;
  combined_score: number;
  safeb_components: SafeBComponents;
  habitat_similarity: number | null;
  strategy: string;
  weights: SafeBComponents;
  native_status: 'native' | 'introduced' | 'invasive' | 'native_and_introduced' | 'unknown';
  is_native: boolean;
  is_introduced: boolean;
  is_invasive: boolean;
  confidence: number;
  sinr_probability: number | null;
  sinr_detail: SinrDetail | null;
  radar: RadarScores;
  discovery_sources: string[];
  attributes: {
    growth_form: string | null;
    successional_stage: string | null;
    ecoregions: string | null;
    conservation_status: string | null;
    cluster_elevation: number | null;
    occurrence_count: number | null;
  };
}

interface LocationContext {
  ecoregion: {
    eco_id: number;
    eco_name: string;
    biome_name: string;
    realm: string;
  };
  countries: string[];
}

interface RecommendationResponse {
  success: boolean;
  location: { latitude: number; longitude: number; elevation: number | null; data_source: string; demo_mode: boolean };
  location_context: LocationContext | null;
  strategy: { name: string; description: string; weights: SafeBComponents };
  results: {
    count: number;
    total_candidates: number;
    excluded_count: number;
    sinr_available: boolean;
    candidate_sources: { embedding: number; spatial: number; strategy_specific: number; sinr_v2: number };
    recommendations: Recommendation[];
    excluded_sample: Array<{ taxon_id: string; scientific_name: string; filter_reason: string }>;
  };
}

interface SpeciesRecommenderModalProps {
  lat: number;
  lon: number;
  onClose: () => void;
}

// ============================================================================
// Strategy Icons / Colors
// ============================================================================

const STRATEGY_META: Record<string, { icon: string; color: string; bgColor: string }> = {
  general: { icon: '🌍', color: 'text-emerald-400', bgColor: 'bg-emerald-500/20' },
  rewilding: { icon: '🦎', color: 'text-green-400', bgColor: 'bg-green-500/20' },
  agroforestry: { icon: '🌾', color: 'text-amber-400', bgColor: 'bg-amber-500/20' },
  riparian: { icon: '💧', color: 'text-blue-400', bgColor: 'bg-blue-500/20' },
  carbon: { icon: '🌲', color: 'text-teal-400', bgColor: 'bg-teal-500/20' },
  biodiversity: { icon: '🦋', color: 'text-purple-400', bgColor: 'bg-purple-500/20' },
  erosion_control: { icon: '🏔️', color: 'text-orange-400', bgColor: 'bg-orange-500/20' },
};

// ============================================================================
// Radar Chart Component
// ============================================================================

const RADAR_AXES = [
  { key: 'sinr_habitat', label: 'SINR', color: '#34d399' },
  { key: 'abiotic', label: 'Climate', color: '#22d3ee' },
  { key: 'ecosystem', label: 'Ecosystem', color: '#a78bfa' },
  { key: 'spatial', label: 'Spatial', color: '#60a5fa' },
  { key: 'biotic', label: 'Biotic', color: '#f472b6' },
  { key: 'functional', label: 'Traits', color: '#fbbf24' },
] as const;

function RadarChart({ scores, size = 140 }: { scores: RadarScores; size?: number }) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 24; // leave room for labels
  const n = RADAR_AXES.length;

  const angleStep = (2 * Math.PI) / n;
  const startAngle = -Math.PI / 2; // start from top

  // Get point on radar for a given axis index and value (0-100)
  const getPoint = (i: number, value: number) => {
    const angle = startAngle + i * angleStep;
    const dist = (value / 100) * r;
    return {
      x: cx + dist * Math.cos(angle),
      y: cy + dist * Math.sin(angle),
    };
  };

  // Grid rings at 25%, 50%, 75%, 100%
  const rings = [25, 50, 75, 100];

  // Build the data polygon
  const values = RADAR_AXES.map(axis => {
    const v = scores[axis.key as keyof RadarScores];
    return v != null ? Math.min(100, Math.max(0, v)) : 0;
  });

  const polyPoints = values.map((v, i) => {
    const pt = getPoint(i, v);
    return `${pt.x},${pt.y}`;
  }).join(' ');

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="flex-shrink-0">
      {/* Grid rings */}
      {rings.map(ring => {
        const pts = Array.from({ length: n }, (_, i) => {
          const pt = getPoint(i, ring);
          return `${pt.x},${pt.y}`;
        }).join(' ');
        return (
          <polygon
            key={ring}
            points={pts}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={ring === 100 ? 1 : 0.5}
          />
        );
      })}

      {/* Axis lines */}
      {RADAR_AXES.map((_, i) => {
        const pt = getPoint(i, 100);
        return (
          <line
            key={i}
            x1={cx} y1={cy}
            x2={pt.x} y2={pt.y}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={0.5}
          />
        );
      })}

      {/* Data polygon */}
      <polygon
        points={polyPoints}
        fill="rgba(52, 211, 153, 0.15)"
        stroke="rgba(52, 211, 153, 0.6)"
        strokeWidth={1.5}
      />

      {/* Data points */}
      {values.map((v, i) => {
        if (v === 0) return null;
        const pt = getPoint(i, v);
        return (
          <circle
            key={i}
            cx={pt.x} cy={pt.y}
            r={2.5}
            fill={RADAR_AXES[i].color}
            stroke="rgba(0,0,0,0.3)"
            strokeWidth={0.5}
          />
        );
      })}

      {/* Labels */}
      {RADAR_AXES.map((axis, i) => {
        const pt = getPoint(i, 115); // slightly outside the chart
        const v = values[i];
        return (
          <text
            key={i}
            x={pt.x}
            y={pt.y}
            textAnchor="middle"
            dominantBaseline="middle"
            className="text-[9px]"
            fill={v > 0 ? axis.color : 'rgba(255,255,255,0.3)'}
          >
            {axis.label}
          </text>
        );
      })}
    </svg>
  );
}

// ============================================================================
// Component
// ============================================================================

export default function SpeciesRecommenderModal({ lat, lon, onClose }: SpeciesRecommenderModalProps) {
  const [status, setStatus] = useState<'loading-strategies' | 'selecting' | 'recommending' | 'complete' | 'error'>('loading-strategies');
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState('general');
  const [includeIntroduced, setIncludeIntroduced] = useState(false);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [locationContext, setLocationContext] = useState<LocationContext | null>(null);
  const [responseData, setResponseData] = useState<RecommendationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [expandedSpecies, setExpandedSpecies] = useState<Set<string>>(new Set());
  const [displayCount, setDisplayCount] = useState(15);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';

  // Load available strategies
  useEffect(() => {
    async function loadStrategies() {
      try {
        const res = await fetch(`${API_URL}/api/prediction/strategies`);
        const data = await res.json();
        if (data.success && data.strategies) {
          setStrategies(data.strategies);
          setStatus('selecting');
        } else {
          // Fallback: hardcoded strategies
          setStrategies([
            { key: 'general', name: 'General', description: 'Balanced scoring', weights: { spatial: 0.2, abiotic: 0.25, functional: 0.2, ecosystem: 0.2, biotic: 0.15 } },
            { key: 'rewilding', name: 'Rewilding', description: 'Native species restoration', weights: { spatial: 0.2, abiotic: 0.15, functional: 0.1, ecosystem: 0.3, biotic: 0.25 } },
            { key: 'agroforestry', name: 'Agroforestry', description: 'Productive tree systems', weights: { spatial: 0.1, abiotic: 0.25, functional: 0.4, ecosystem: 0.15, biotic: 0.1 } },
            { key: 'carbon', name: 'Carbon', description: 'Maximum carbon sequestration', weights: { spatial: 0.1, abiotic: 0.2, functional: 0.5, ecosystem: 0.15, biotic: 0.05 } },
            { key: 'biodiversity', name: 'Biodiversity', description: 'Species diversity', weights: { spatial: 0.15, abiotic: 0.15, functional: 0.2, ecosystem: 0.25, biotic: 0.25 } },
            { key: 'riparian', name: 'Riparian', description: 'Waterway restoration', weights: { spatial: 0.15, abiotic: 0.35, functional: 0.2, ecosystem: 0.2, biotic: 0.1 } },
            { key: 'erosion_control', name: 'Erosion Control', description: 'Soil stabilization', weights: { spatial: 0.15, abiotic: 0.3, functional: 0.3, ecosystem: 0.15, biotic: 0.1 } },
          ]);
          setStatus('selecting');
        }
      } catch {
        // Use hardcoded fallback
        setStrategies([
          { key: 'general', name: 'General', description: 'Balanced scoring', weights: { spatial: 0.2, abiotic: 0.25, functional: 0.2, ecosystem: 0.2, biotic: 0.15 } },
        ]);
        setStatus('selecting');
      }
    }
    loadStrategies();
  }, [API_URL]);

  // Run recommendation
  async function runRecommendation() {
    setStatus('recommending');
    try {
      const params = new URLSearchParams({
        lat: lat.toString(),
        lon: lon.toString(),
        strategy: selectedStrategy,
        include_introduced: includeIntroduced.toString(),
        limit: '50'
      });

      const res = await fetch(`${API_URL}/api/prediction/recommend?${params}`);
      const data: RecommendationResponse = await res.json();

      if (data.success) {
        setRecommendations(data.results.recommendations);
        setLocationContext(data.location_context);
        setResponseData(data);
        setStatus('complete');
      } else {
        setErrorMessage((data as any).error || 'Recommendation failed');
        setStatus('error');
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Network error');
      setStatus('error');
    }
  }

  const toggleExpanded = (taxonId: string) => {
    setExpandedSpecies(prev => {
      const next = new Set(prev);
      if (next.has(taxonId)) next.delete(taxonId);
      else next.add(taxonId);
      return next;
    });
  };

  const nativeStatusBadge = (status: string) => {
    switch (status) {
      case 'native': return <span className="px-2 py-0.5 text-xs rounded-full bg-green-500/20 text-green-400 border border-green-500/30">Native</span>;
      case 'introduced': return <span className="px-2 py-0.5 text-xs rounded-full bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">Introduced</span>;
      case 'invasive': return <span className="px-2 py-0.5 text-xs rounded-full bg-red-500/20 text-red-400 border border-red-500/30">Invasive</span>;
      case 'native_and_introduced': return <span className="px-2 py-0.5 text-xs rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">Native+Intro</span>;
      default: return <span className="px-2 py-0.5 text-xs rounded-full bg-gray-500/20 text-gray-400 border border-gray-500/30">Unknown</span>;
    }
  };

  const safebBar = (label: string, value: number, color: string) => (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-white/50">{label}</span>
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="w-8 text-right text-white/60">{value}</span>
    </div>
  );

  // ============================================================================
  // Render
  // ============================================================================

  const modalContent = (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-gray-900/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/20">
              <TreePine className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Species Recommender</h2>
              <p className="text-xs text-white/50">
                {lat.toFixed(4)}, {lon.toFixed(4)}
                {locationContext?.ecoregion && ` - ${locationContext.ecoregion.eco_name}`}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/10 transition-colors">
            <X className="w-5 h-5 text-white/70" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Strategy Selection */}
          {(status === 'selecting' || status === 'complete') && (
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-white/80">Restoration Strategy</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {strategies.map(s => {
                  const meta = STRATEGY_META[s.key] || STRATEGY_META.general;
                  const isSelected = selectedStrategy === s.key;
                  return (
                    <button
                      key={s.key}
                      onClick={() => {
                        setSelectedStrategy(s.key);
                        if (status === 'complete') runRecommendation();
                      }}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        isSelected
                          ? `${meta.bgColor} border-white/30 ring-1 ring-white/20`
                          : 'bg-white/5 border-white/10 hover:bg-white/10'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{meta.icon}</span>
                        <span className={`text-sm font-medium ${isSelected ? meta.color : 'text-white/70'}`}>
                          {s.name}
                        </span>
                      </div>
                      <p className="text-xs text-white/40 mt-1 line-clamp-1">{s.description}</p>
                    </button>
                  );
                })}
              </div>

              {/* Options */}
              <div className="flex items-center gap-4 pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeIntroduced}
                    onChange={(e) => setIncludeIntroduced(e.target.checked)}
                    className="w-4 h-4 rounded border-white/30 bg-white/10 text-emerald-500 focus:ring-emerald-500/50"
                  />
                  <span className="text-sm text-white/60">Include introduced species</span>
                </label>

                {status === 'selecting' && (
                  <button
                    onClick={runRecommendation}
                    className="ml-auto px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-colors flex items-center gap-2"
                  >
                    <Target className="w-4 h-4" />
                    Get Recommendations
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Loading */}
          {status === 'recommending' && (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <Loader2 className="w-10 h-10 text-emerald-400 animate-spin" />
              <p className="text-white/70">Analyzing habitat suitability...</p>
              <p className="text-xs text-white/40">SINR v2.2 neural prediction + SAFE-B scoring</p>
            </div>
          )}

          {/* Loading strategies */}
          {status === 'loading-strategies' && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-emerald-400 animate-spin mr-3" />
              <span className="text-white/60">Loading strategies...</span>
            </div>
          )}

          {/* Error */}
          {status === 'error' && (
            <div className="flex flex-col items-center justify-center py-12 space-y-3">
              <AlertTriangle className="w-10 h-10 text-red-400" />
              <p className="text-red-400 font-medium">Recommendation Failed</p>
              <p className="text-sm text-white/50">{errorMessage}</p>
              <button
                onClick={() => setStatus('selecting')}
                className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm"
              >
                Try Again
              </button>
            </div>
          )}

          {/* Results */}
          {status === 'complete' && responseData && (
            <>
              {/* Summary bar */}
              <div className="flex items-center justify-between bg-white/5 rounded-xl px-4 py-3">
                <div className="flex items-center gap-4">
                  <span className="text-sm text-white/60">
                    <span className="text-emerald-400 font-semibold">{responseData.results.count}</span> recommended
                  </span>
                  <span className="text-sm text-white/40">
                    of {responseData.results.total_candidates} candidates
                  </span>
                  {responseData.results.excluded_count > 0 && (
                    <span className="text-sm text-white/40">
                      ({responseData.results.excluded_count} excluded)
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {responseData.results.sinr_available && (
                    <span className="px-2 py-1 text-xs rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                      <Sparkles className="w-3 h-3" />
                      SINR v2.2
                    </span>
                  )}
                  {responseData.location.demo_mode && (
                    <span className="px-2 py-1 text-xs rounded-full bg-red-500/20 text-red-400 border border-red-500/30 font-semibold">
                      Simulated Data
                    </span>
                  )}
                </div>
              </div>

              {/* Simulated data warning */}
              {responseData.location.demo_mode && (
                <div className="px-4 py-3 bg-red-900/40 border-2 border-red-500/60 rounded-xl">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold text-red-400">
                        SIMULATED DATA - Recommendations are not meaningful
                      </p>
                      <p className="text-xs text-red-300/70 mt-1">
                        No satellite data exists for this location (likely ocean or outside coverage). 
                        Results are based on synthetic noise, not real habitat analysis.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Location context */}
              {locationContext?.ecoregion && (
                <div className="bg-white/5 rounded-xl px-4 py-3 space-y-1">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-blue-400" />
                    <span className="text-sm text-blue-400 font-medium">{locationContext.ecoregion.eco_name}</span>
                  </div>
                  <p className="text-xs text-white/40">
                    {locationContext.ecoregion.biome_name} | {locationContext.ecoregion.realm}
                    {locationContext.countries.length > 0 && ` | ${locationContext.countries.join(', ')}`}
                  </p>
                </div>
              )}

              {/* Re-run with different strategy */}
              <button
                onClick={runRecommendation}
                className="w-full px-4 py-2 rounded-lg bg-emerald-600/20 border border-emerald-500/30 hover:bg-emerald-600/30 text-emerald-400 text-sm font-medium transition-colors"
              >
                Re-run with {strategies.find(s => s.key === selectedStrategy)?.name || selectedStrategy} strategy
              </button>

              {/* Species list */}
              <div className="space-y-2">
                {recommendations.slice(0, displayCount).map((rec) => {
                  const isExpanded = expandedSpecies.has(rec.taxon_id);
                  const meta = STRATEGY_META[selectedStrategy] || STRATEGY_META.general;

                  return (
                    <div
                      key={rec.taxon_id}
                      className="bg-white/5 border border-white/10 rounded-xl overflow-hidden hover:border-white/20 transition-colors"
                    >
                      {/* Species header */}
                      <div
                        className="px-4 py-3 cursor-pointer"
                        onClick={() => toggleExpanded(rec.taxon_id)}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <div className={`w-10 h-10 rounded-lg ${meta.bgColor} flex items-center justify-center text-lg font-bold ${meta.color}`}>
                              {rec.rank}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <Link
                                  href={`/species/${rec.taxon_id}`}
                                  className="text-sm font-medium text-white hover:text-emerald-400 truncate"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  {rec.scientific_name || 'Unknown'}
                                </Link>
                                {nativeStatusBadge(rec.native_status)}
                              </div>
                              <div className="flex items-center gap-2 mt-0.5">
                                {rec.common_name && (
                                  <span className="text-xs text-white/40">{rec.common_name}</span>
                                )}
                                {rec.family && (
                                  <span className="text-xs text-white/30">({rec.family})</span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Score */}
                          <div className="flex items-center gap-3">
                            <div className="text-right">
                              <div className={`text-lg font-bold ${meta.color}`}>{rec.combined_score ?? rec.safeb_score}</div>
                              <div className="text-xs text-white/40">
                                {rec.sinr_probability != null ? 'Score' : 'SAFE-B'}
                              </div>
                            </div>
                            {isExpanded ? (
                              <ChevronUp className="w-4 h-4 text-white/40" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-white/40" />
                            )}
                          </div>
                        </div>

                        {/* Compact indicator row */}
                        <div className="mt-2 flex items-center gap-2">
                          {rec.sinr_probability != null && (
                            <span className="px-1.5 py-0.5 text-[10px] rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/20">
                              SINR {Math.round(rec.sinr_probability * 100)}%
                            </span>
                          )}
                          <div className="flex-1 h-1.5 flex rounded-full overflow-hidden bg-white/5">
                            <div className="bg-blue-500" style={{ width: `${rec.safeb_components.spatial * rec.weights.spatial}%` }} title="Spatial" />
                            <div className="bg-cyan-500" style={{ width: `${rec.safeb_components.abiotic * rec.weights.abiotic}%` }} title="Abiotic" />
                            <div className="bg-amber-500" style={{ width: `${rec.safeb_components.functional * rec.weights.functional}%` }} title="Functional" />
                            <div className="bg-purple-500" style={{ width: `${rec.safeb_components.ecosystem * rec.weights.ecosystem}%` }} title="Ecosystem" />
                            <div className="bg-pink-500" style={{ width: `${rec.safeb_components.biotic * rec.weights.biotic}%` }} title="Biotic" />
                          </div>
                          {rec.discovery_sources?.includes('sinr') && (
                            <Sparkles className="w-3 h-3 text-emerald-500/50" />
                          )}
                        </div>
                      </div>

                      {/* Expanded details */}
                      {isExpanded && (
                        <div className="px-4 pb-4 pt-1 space-y-3 border-t border-white/5">
                          {/* Radar chart + SAFE-B bars side by side */}
                          <div className="flex gap-4">
                            {/* Radar chart */}
                            {rec.radar && (
                              <RadarChart scores={rec.radar} size={140} />
                            )}

                            {/* Score bars */}
                            <div className="flex-1 space-y-1.5">
                              <h4 className="text-xs font-medium text-white/60 uppercase tracking-wider">Scoring Breakdown</h4>
                              {rec.radar?.sinr_habitat != null && safebBar('SINR Habitat', rec.radar.sinr_habitat, 'bg-emerald-500')}
                              {safebBar('Climate/Soil', rec.safeb_components.abiotic, 'bg-cyan-500')}
                              {safebBar('Ecosystem', rec.safeb_components.ecosystem, 'bg-purple-500')}
                              {safebBar('Spatial', rec.safeb_components.spatial, 'bg-blue-500')}
                              {safebBar('Traits', rec.safeb_components.functional, 'bg-amber-500')}
                              {safebBar('Biotic', rec.safeb_components.biotic, 'bg-pink-500')}
                            </div>
                          </div>

                          {/* SINR detail + Confidence */}
                          <div className="flex items-center gap-3 flex-wrap text-xs text-white/50">
                            {rec.sinr_probability != null && (
                              <span className="text-emerald-400">
                                SINR: {(rec.sinr_probability * 100).toFixed(1)}%
                                {rec.sinr_detail && ` (native: ${(rec.sinr_detail.prob_native * 100).toFixed(1)}% / intro: ${(rec.sinr_detail.prob_introduced * 100).toFixed(1)}%)`}
                              </span>
                            )}
                            <span>SAFE-B: {rec.safeb_score}</span>
                            <span>Confidence: {rec.confidence}%</span>
                            {rec.attributes.occurrence_count && (
                              <span>{rec.attributes.occurrence_count.toLocaleString()} occurrences</span>
                            )}
                          </div>

                          {/* Discovery sources */}
                          {rec.discovery_sources && rec.discovery_sources.length > 0 && (
                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] text-white/30 uppercase">Found via:</span>
                              {rec.discovery_sources.map(src => (
                                <span key={src} className="px-1.5 py-0.5 text-[10px] rounded bg-white/5 text-white/40 border border-white/10">
                                  {src === 'sinr' ? 'SINR v2.2' : src}
                                </span>
                              ))}
                            </div>
                          )}

                          {/* Attributes */}
                          <div className="flex flex-wrap gap-2">
                            {rec.attributes.growth_form && rec.attributes.growth_form !== 'NA' && (
                              <span className="px-2 py-0.5 text-xs rounded-full bg-white/5 text-white/50 border border-white/10">
                                {rec.attributes.growth_form}
                              </span>
                            )}
                            {rec.attributes.successional_stage && rec.attributes.successional_stage !== 'NA' && (
                              <span className="px-2 py-0.5 text-xs rounded-full bg-white/5 text-white/50 border border-white/10">
                                {rec.attributes.successional_stage}
                              </span>
                            )}
                            {rec.attributes.conservation_status && rec.attributes.conservation_status !== 'NA' && (
                              <span className="px-2 py-0.5 text-xs rounded-full bg-white/5 text-white/50 border border-white/10">
                                {rec.attributes.conservation_status}
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Show more */}
                {displayCount < recommendations.length && (
                  <button
                    onClick={() => setDisplayCount(prev => prev + 15)}
                    className="w-full py-3 text-sm text-white/50 hover:text-white/70 hover:bg-white/5 rounded-xl transition-colors"
                  >
                    Show more ({recommendations.length - displayCount} remaining)
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );

  if (typeof window === 'undefined') return null;
  return createPortal(modalContent, document.body);
}
