'use client';

import { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X, Loader2, MapPin, Sparkles, Leaf, AlertTriangle, Globe } from 'lucide-react';
import Link from 'next/link';
import L from 'leaflet';

interface AlternateHabitat {
  cluster_id: number;
  cluster_size: number;
  representative_lat: number;
  representative_lon: number;
  similarity_score: string;
  confidence: number;
}

interface SpeciesPrediction {
  rank: number;
  taxon_id: string;
  scientific_name: string;
  species_scientific_name?: string; // legacy compat
  family: string;
  common_name: string | null;
  genus?: string;
  suitability_score: number;
  habitat_similarity: number;
  signals?: {
    embedding: number;
    spatial: number;
    range: number;
    ecoregion: number;
    climate: number;
  };
  discovery_sources?: string[];
  source_count?: number;
  raw_embedding_similarity?: number;
  spatial_tiles_nearby?: number;
  spatial_min_distance_m?: number | null;
  cluster_id?: number;
  cluster_size?: number;
  total_occurrences?: number;
  representative_lat?: number;
  representative_lon?: number;
  similarity_score?: string;
  confidence?: number;
  habitat_count?: number;
  alternate_habitats?: AlternateHabitat[];
  habitat_match?: {
    cluster_id: number;
    cluster_elevation: number;
    cluster_treecover: number;
    cluster_occurrences: number;
    representative_location: { lat: number; lon: number } | null;
  };
  native_status?: 'native' | 'introduced' | 'invasive' | 'native_and_introduced' | 'unknown';
  is_native?: boolean;
  is_introduced?: boolean;
  is_invasive?: boolean;
  ecoregion_match?: boolean;
  signal_weights?: {
    embedding: number;
    spatial: number;
    range: number;
    ecoregion: number;
    climate: number;
  };
  attributes?: {
    growth_form: string | null;
    maximum_height: string | null;
    conservation_status: string | null;
  };
}

interface LocationContext {
  ecoregion: {
    eco_id: number;
    eco_name: string;
    biome_name: string;
    realm: string;
  } | null;
  countries: string[];
  climate?: {
    annual_mean_temp_c: number | null;
    annual_precipitation_mm: number | null;
  } | null;
  soil?: {
    ph: number | null;
    ph_category: string | null;
    texture: string | null;
  } | null;
}

type NativeStatusFilter = 'native' | 'introduced' | 'invasive' | 'unknown';

interface NativeStatusSummary {
  native: number;
  introduced: number;
  invasive: number;
  native_and_introduced: number;
  unknown: number;
}

interface PredictionResponse {
  success: boolean;
  prediction_count?: number;
  location?: {
    latitude: number;
    longitude: number;
    elevation: number | null;
    data_source: string;
    demo_mode: boolean;
  };
  results?: {
    count: number;
    native_status_summary: NativeStatusSummary;
    source_summary?: {
      embedding_only: number;
      spatial_only: number;
      multi_source: number;
      total_candidates_evaluated: number;
    };
    predictions: SpeciesPrediction[];
  };
  // Legacy format support
  predictions?: SpeciesPrediction[];
  location_context?: LocationContext | null;
  native_status_summary?: NativeStatusSummary;
}

interface HabitatPredictionModalProps {
  lat: number;
  lon: number;
  onClose: () => void;
  map?: L.Map | null;
}

export default function HabitatPredictionModal({ lat, lon, onClose, map }: HabitatPredictionModalProps) {
  const [status, setStatus] = useState<'sampling' | 'predicting' | 'complete' | 'error'>('sampling');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('Initializing...');
  const [predictions, setPredictions] = useState<SpeciesPrediction[]>([]);
  const [locationContext, setLocationContext] = useState<LocationContext | null>(null);
  const [nativeStatusSummary, setNativeStatusSummary] = useState<NativeStatusSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [expandedSpecies, setExpandedSpecies] = useState<Set<string>>(new Set());
  const [displayCount, setDisplayCount] = useState(30);
  const [mounted, setMounted] = useState(false);
  const [activeFilters, setActiveFilters] = useState<Set<NativeStatusFilter>>(new Set());
  const modalRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  const toggleExpanded = (taxonId: string) => {
    setExpandedSpecies(prev => {
      const next = new Set(prev);
      if (next.has(taxonId)) {
        next.delete(taxonId);
      } else {
        next.add(taxonId);
      }
      return next;
    });
  };

  const toggleFilter = (filter: NativeStatusFilter) => {
    setActiveFilters(prev => {
      const next = new Set(prev);
      if (next.has(filter)) {
        next.delete(filter);
      } else {
        next.add(filter);
      }
      return next;
    });
    // Reset display count when filters change
    setDisplayCount(30);
  };

  // Categorize a prediction's native status for filtering
  const getNativeCategory = (pred: SpeciesPrediction): NativeStatusFilter => {
    if (pred.native_status === 'native' || pred.native_status === 'native_and_introduced') return 'native';
    if (pred.native_status === 'introduced') return 'introduced';
    if (pred.native_status === 'invasive') return 'invasive';
    return 'unknown';
  };

  // Apply filters — if no filters active, show all
  const filteredPredictions = activeFilters.size === 0
    ? predictions
    : predictions.filter(p => activeFilters.has(getNativeCategory(p)));

  // Handle client-side mounting for portal
  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  // Disable map interactions and use Leaflet's DomEvent to block propagation
  useEffect(() => {
    // Disable Leaflet map interactions when modal is open
    if (map) {
      map.scrollWheelZoom.disable();
      map.dragging.disable();
      map.touchZoom.disable();
      map.doubleClickZoom.disable();
      map.boxZoom.disable();
      map.keyboard.disable();
    }

    // Use Leaflet's DomEvent utilities to prevent event propagation to map
    if (modalRef.current) {
      L.DomEvent.disableClickPropagation(modalRef.current);
      L.DomEvent.disableScrollPropagation(modalRef.current);
    }

    if (overlayRef.current) {
      L.DomEvent.disableClickPropagation(overlayRef.current);
      L.DomEvent.disableScrollPropagation(overlayRef.current);
    }

    // Prevent body scroll
    document.body.style.overflow = 'hidden';

    return () => {
      // Re-enable map interactions when modal closes
      if (map) {
        map.scrollWheelZoom.enable();
        map.dragging.enable();
        map.touchZoom.enable();
        map.doubleClickZoom.enable();
        map.boxZoom.enable();
        map.keyboard.enable();
      }

      document.body.style.overflow = '';
    };
  }, [map]);

  useEffect(() => {
    console.log('🔄 Habitat prediction starting for:', lat.toFixed(4), lon.toFixed(4));

    // Reset state for new prediction
    setStatus('sampling');
    setProgress(0);
    setMessage('Initializing...');
    setPredictions([]);
    setErrorMessage('');
    setIsDemoMode(false);
    setActiveFilters(new Set());
    setDisplayCount(30);

    sampleAndPredict();
  }, [lat, lon]);

  const sampleAndPredict = async () => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';

    try {
      // Step 1: UI feedback
      setMessage('Analyzing location with multi-signal prediction...');
      setProgress(10);
      setStatus('sampling');
      await new Promise(resolve => setTimeout(resolve, 100));

      setMessage('Sampling AlphaEarth satellite data + occurrence records...');
      setProgress(20);
      await new Promise(resolve => setTimeout(resolve, 100));

      setMessage('This may take 10-30 seconds (Earth Engine + spatial queries)...');
      setProgress(30);

      console.log('Calling multi-signal predict endpoint...');
      const startTime = Date.now();

      // Single call to the new multi-signal predict endpoint
      // It handles: GEE sampling + embedding + spatial + WCVP + ecoregion
      const response = await fetch(
        `${API_URL}/api/prediction/predict?lat=${lat}&lon=${lon}&limit=100`
      );

      const duration = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log(`Prediction completed in ${duration}s`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || errorData.detail || `Server error: ${response.status}`);
      }

      setMessage('Processing multi-signal results...');
      setProgress(80);
      await new Promise(resolve => setTimeout(resolve, 100));

      const data: PredictionResponse = await response.json();

      if (!data.success) {
        throw new Error((data as any).error || 'Prediction failed');
      }

      // Check demo mode
      if (data.location?.demo_mode) {
        setIsDemoMode(true);
      }

      // Extract predictions from new format
      const preds = data.results?.predictions || data.predictions || [];
      const locContext = data.location_context || null;
      const nativeSummary = data.results?.native_status_summary || data.native_status_summary || null;

      console.log(`Received ${preds.length} predictions from ${data.results?.source_summary?.total_candidates_evaluated || '?'} candidates`);
      if (data.results?.source_summary) {
        const ss = data.results.source_summary;
        console.log(`Sources: ${ss.embedding_only} emb-only, ${ss.spatial_only} spatial-only, ${ss.multi_source} multi-source`);
      }

      setMessage('Species predictions ready!');
      setProgress(100);
      setPredictions(preds);
      setLocationContext(locContext);
      setNativeStatusSummary(nativeSummary);
      setStatus('complete');

    } catch (error) {
      console.error('Prediction error:', error);
      setStatus('error');
      setErrorMessage(error instanceof Error ? error.message : 'An unknown error occurred');
      setProgress(100);
    }
  };

  const modalContent = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={modalRef}
        className="relative w-full max-w-3xl max-h-[90vh] bg-gradient-to-br from-emerald-950 to-black border border-emerald-500/30 shadow-2xl rounded-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex-shrink-0 bg-gradient-to-r from-emerald-900/90 to-emerald-800/90 backdrop-blur-md px-6 py-4 border-b border-emerald-500/20 rounded-t-2xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Sparkles className="h-6 w-6 text-emerald-300" />
              <div>
                <h2 className="text-xl font-semibold text-white">Species Prediction</h2>
                <p className="text-sm text-emerald-200">
                  <MapPin className="inline h-3 w-3 mr-1" />
                  {lat.toFixed(4)}, {lon.toFixed(4)}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-emerald-300 hover:text-white transition-colors"
            >
              <X className="h-6 w-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 overflow-y-auto">
          {/* Loading State - show while sampling or predicting */}
          {(status === 'sampling' || status === 'predicting') && (
            <div className="space-y-4">
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-12 w-12 text-emerald-400 animate-spin" />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-emerald-300">{message}</span>
                  <span className="text-emerald-400 font-medium">{progress}%</span>
                </div>
                <div className="h-2 bg-emerald-950 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-500 to-emerald-300 transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>

              <p className="text-sm text-center text-emerald-200/70">
                {status === 'sampling' && 'Sampling satellite data from Google Earth Engine...'}
                {status === 'predicting' && 'Comparing habitat signature to species database...'}
              </p>
            </div>
          )}

          {/* Error State */}
          {status === 'error' && (
            <div className="py-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 mb-4">
                <X className="h-8 w-8 text-red-400" />
              </div>
              <h3 className="text-lg font-medium text-white mb-2">Prediction Failed</h3>
              <p className="text-emerald-200/70 mb-4">{errorMessage}</p>
              <button
                onClick={onClose}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          )}

          {/* Success State - Predictions */}
          {status === 'complete' && predictions.length > 0 && (
            <div className="space-y-4">
              <div className="text-center mb-6">
                <h3 className="text-lg font-medium text-white mb-2">
                  Top {predictions.length} Species Predictions
                </h3>
                <p className="text-sm text-emerald-200/70">
                  Multi-signal: satellite + spatial + range + ecoregion + climate + soil
                </p>
                {isDemoMode && (
                  <div className="mt-3 px-4 py-3 bg-red-900/40 border-2 border-red-500/60 rounded-xl">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-semibold text-red-400">
                          SIMULATED DATA - Predictions are not meaningful
                        </p>
                        <p className="text-xs text-red-300/70 mt-1">
                          No satellite data exists for this location (likely ocean or outside coverage). 
                          The embedding was generated synthetically and results are random noise, not real habitat analysis.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Location Context & Native Status Filters */}
              {(locationContext || nativeStatusSummary) && (
                <div className="bg-black/30 rounded-xl p-4 border border-emerald-500/20 mb-4">
                  {locationContext?.ecoregion && (
                    <div className="mb-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Globe className="h-4 w-4 text-emerald-400" />
                        <span className="text-sm font-medium text-white">{locationContext.ecoregion.eco_name}</span>
                      </div>
                      <p className="text-xs text-emerald-300/60 ml-6">
                        {locationContext.ecoregion.biome_name} • {locationContext.ecoregion.realm}
                        {locationContext.countries?.length > 0 && ` • ${locationContext.countries.join(', ')}`}
                      </p>
                    </div>
                  )}

                  {/* Climate & Soil context */}
                  {(locationContext?.climate || locationContext?.soil) && (
                    <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3 ml-6 text-xs text-emerald-300/50">
                      {locationContext.climate?.annual_mean_temp_c != null && (
                        <span>{locationContext.climate.annual_mean_temp_c.toFixed(1)}°C</span>
                      )}
                      {locationContext.climate?.annual_precipitation_mm != null && (
                        <span>{Math.round(locationContext.climate.annual_precipitation_mm)}mm/yr</span>
                      )}
                      {locationContext.soil?.ph != null && (
                        <span>pH {locationContext.soil.ph} ({locationContext.soil.ph_category})</span>
                      )}
                      {locationContext.soil?.texture && (
                        <span>{locationContext.soil.texture}</span>
                      )}
                    </div>
                  )}

                  {/* Toggleable native status filters */}
                  {nativeStatusSummary && (
                    <div>
                      <div className="flex flex-wrap gap-2">
                        {nativeStatusSummary.native > 0 && (
                          <button
                            onClick={() => toggleFilter('native')}
                            className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs transition-all cursor-pointer ${
                              activeFilters.has('native')
                                ? 'bg-green-500/40 text-green-200 ring-1 ring-green-400/60'
                                : activeFilters.size > 0
                                  ? 'bg-green-500/10 text-green-400/40'
                                  : 'bg-green-500/20 text-green-300 hover:bg-green-500/30'
                            }`}
                          >
                            <Leaf className="h-3 w-3" />
                            {nativeStatusSummary.native} Native
                          </button>
                        )}
                        {nativeStatusSummary.introduced > 0 && (
                          <button
                            onClick={() => toggleFilter('introduced')}
                            className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs transition-all cursor-pointer ${
                              activeFilters.has('introduced')
                                ? 'bg-blue-500/40 text-blue-200 ring-1 ring-blue-400/60'
                                : activeFilters.size > 0
                                  ? 'bg-blue-500/10 text-blue-400/40'
                                  : 'bg-blue-500/20 text-blue-300 hover:bg-blue-500/30'
                            }`}
                          >
                            <Globe className="h-3 w-3" />
                            {nativeStatusSummary.introduced} Introduced
                          </button>
                        )}
                        {nativeStatusSummary.invasive > 0 && (
                          <button
                            onClick={() => toggleFilter('invasive')}
                            className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs transition-all cursor-pointer ${
                              activeFilters.has('invasive')
                                ? 'bg-red-500/40 text-red-200 ring-1 ring-red-400/60'
                                : activeFilters.size > 0
                                  ? 'bg-red-500/10 text-red-400/40'
                                  : 'bg-red-500/20 text-red-300 hover:bg-red-500/30'
                            }`}
                          >
                            <AlertTriangle className="h-3 w-3" />
                            {nativeStatusSummary.invasive} Invasive
                          </button>
                        )}
                        {nativeStatusSummary.unknown > 0 && (
                          <button
                            onClick={() => toggleFilter('unknown')}
                            className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs transition-all cursor-pointer ${
                              activeFilters.has('unknown')
                                ? 'bg-gray-500/40 text-gray-200 ring-1 ring-gray-400/60'
                                : activeFilters.size > 0
                                  ? 'bg-gray-500/10 text-gray-400/40'
                                  : 'bg-gray-500/20 text-gray-300 hover:bg-gray-500/30'
                            }`}
                          >
                            {nativeStatusSummary.unknown} Unknown
                          </button>
                        )}
                        {activeFilters.size > 0 && (
                          <button
                            onClick={() => setActiveFilters(new Set())}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/70 transition-all cursor-pointer"
                          >
                            <X className="h-3 w-3" />
                            Clear
                          </button>
                        )}
                      </div>
                      {activeFilters.size > 0 && (
                        <p className="text-xs text-emerald-300/40 mt-2">
                          Showing {filteredPredictions.length} of {predictions.length} species
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-3">
                {filteredPredictions.slice(0, displayCount).map((pred, index) => {
                  const isExpanded = expandedSpecies.has(pred.taxon_id);
                  const displayName = pred.scientific_name || pred.species_scientific_name || 'Unknown';
                  const score = pred.suitability_score || (pred.confidence ? Math.round(pred.confidence * 100) : 0);
                  const signals = pred.signals;
                  const sources = pred.discovery_sources || [];

                  return (
                    <div key={`${pred.taxon_id}-${index}`} className="bg-black/30 backdrop-blur-sm border border-emerald-500/20 rounded-xl hover:border-emerald-400/40 transition-all">
                      <div className="p-4">
                        <Link href={`/species/${pred.taxon_id}`} className="block hover:bg-black/20 transition-all cursor-pointer -m-1 p-1 rounded-lg">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1 flex-wrap">
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-bold">
                                  {pred.rank || index + 1}
                                </span>
                                <h4 className="text-white font-medium italic">
                                  {displayName}
                                </h4>
                                {/* Native Status Badge */}
                                {pred.native_status === 'native' && (
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-green-500/20 text-green-300 text-xs">
                                    <Leaf className="h-2.5 w-2.5" />
                                    Native
                                  </span>
                                )}
                                {pred.native_status === 'introduced' && (
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 text-xs">
                                    <Globe className="h-2.5 w-2.5" />
                                    Introduced
                                  </span>
                                )}
                                {pred.native_status === 'invasive' && (
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 text-xs">
                                    <AlertTriangle className="h-2.5 w-2.5" />
                                    Invasive
                                  </span>
                                )}
                                {pred.native_status === 'native_and_introduced' && (
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-300 text-xs">
                                    <Leaf className="h-2.5 w-2.5" />
                                    Native+Intro
                                  </span>
                                )}
                                {pred.ecoregion_match && (
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-xs">
                                    Ecoregion
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-emerald-300/70 ml-8">
                                {pred.family}
                                {pred.common_name && ` • ${pred.common_name.split(';')[0].trim()}`}
                              </p>
                            </div>
                            <div className="text-right">
                              <div className="text-lg font-bold text-emerald-400">
                                {score}%
                              </div>
                              <div className="text-xs text-emerald-300/50">
                                suitability
                              </div>
                            </div>
                          </div>
                        </Link>

                        {/* Multi-signal score bar */}
                        {signals ? (
                          <div className="h-2 flex rounded-full overflow-hidden bg-emerald-950/50 mb-2">
                            {signals.embedding > 0 && (
                              <div className="bg-blue-500 h-full" style={{ width: `${signals.embedding * (pred.signal_weights?.embedding || 0.3)}%` }} title={`Embedding: ${signals.embedding}%`} />
                            )}
                            {signals.spatial > 0 && (
                              <div className="bg-amber-500 h-full" style={{ width: `${signals.spatial * (pred.signal_weights?.spatial || 0.3)}%` }} title={`Spatial: ${signals.spatial}%`} />
                            )}
                            {signals.range > 0 && (
                              <div className="bg-green-500 h-full" style={{ width: `${signals.range * (pred.signal_weights?.range || 0.15)}%` }} title={`Range: ${signals.range}%`} />
                            )}
                            {signals.ecoregion > 0 && (
                              <div className="bg-purple-500 h-full" style={{ width: `${signals.ecoregion * (pred.signal_weights?.ecoregion || 0.15)}%` }} title={`Ecoregion: ${signals.ecoregion}%`} />
                            )}
                            {signals.climate > 0 && (
                              <div className="bg-teal-500 h-full" style={{ width: `${signals.climate * (pred.signal_weights?.climate || 0.1)}%` }} title={`Climate: ${signals.climate}%`} />
                            )}
                          </div>
                        ) : (
                          <div className="h-1.5 bg-emerald-950/50 rounded-full overflow-hidden mb-3">
                            <div
                              className="h-full bg-gradient-to-r from-emerald-500 to-emerald-300 transition-all duration-300"
                              style={{ width: `${score}%` }}
                            />
                          </div>
                        )}

                        {/* Discovery sources + key signals */}
                        <div className="flex items-center justify-between text-xs text-emerald-200/50">
                          <div className="flex items-center gap-2">
                            {sources.includes('embedding') && (
                              <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300/70">Satellite</span>
                            )}
                            {sources.includes('spatial') && (
                              <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300/70">
                                Observed nearby
                                {pred.spatial_tiles_nearby ? ` (${pred.spatial_tiles_nearby} tiles)` : ''}
                              </span>
                            )}
                            {pred.raw_embedding_similarity != null && pred.raw_embedding_similarity > 0 && (
                              <span>emb:{Math.round(pred.raw_embedding_similarity * 100)}%</span>
                            )}
                          </div>
                          {pred.habitat_match?.representative_location && (
                            <span>
                              <MapPin className="inline h-3 w-3 mr-1" />
                              {pred.habitat_match.representative_location.lat.toFixed(2)}, {pred.habitat_match.representative_location.lon.toFixed(2)}
                            </span>
                          )}
                        </div>

                        {/* Expandable signal breakdown */}
                        {signals && (
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              toggleExpanded(pred.taxon_id);
                            }}
                            className="w-full mt-2 py-1.5 text-xs text-emerald-400 hover:text-emerald-300 border-t border-emerald-500/10 hover:bg-black/20 transition-colors"
                          >
                            {isExpanded ? '▼ Hide signals' : '▶ Show signal breakdown'}
                          </button>
                        )}
                        {isExpanded && signals && (
                          <div className="mt-2 pt-2 border-t border-emerald-500/10 space-y-1.5">
                            <div className="flex items-center gap-2 text-xs">
                              <span className="w-20 text-blue-400">Satellite</span>
                              <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                                <div className="h-full rounded-full bg-blue-500" style={{ width: `${signals.embedding}%` }} />
                              </div>
                              <span className="w-8 text-right text-white/50">{signals.embedding}</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                              <span className="w-20 text-amber-400">Spatial</span>
                              <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                                <div className="h-full rounded-full bg-amber-500" style={{ width: `${signals.spatial}%` }} />
                              </div>
                              <span className="w-8 text-right text-white/50">{signals.spatial}</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                              <span className="w-20 text-green-400">Range</span>
                              <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                                <div className="h-full rounded-full bg-green-500" style={{ width: `${signals.range}%` }} />
                              </div>
                              <span className="w-8 text-right text-white/50">{signals.range}</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                              <span className="w-20 text-purple-400">Ecoregion</span>
                              <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                                <div className="h-full rounded-full bg-purple-500" style={{ width: `${signals.ecoregion}%` }} />
                              </div>
                              <span className="w-8 text-right text-white/50">{signals.ecoregion}</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                              <span className="w-20 text-teal-400">Climate</span>
                              <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                                <div className="h-full rounded-full bg-teal-500" style={{ width: `${signals.climate}%` }} />
                              </div>
                              <span className="w-8 text-right text-white/50">{signals.climate}</span>
                            </div>
                            {pred.spatial_min_distance_m != null && (
                              <p className="text-xs text-white/40 mt-1">
                                Nearest occurrence: {pred.spatial_min_distance_m < 1000 ? `${pred.spatial_min_distance_m}m` : `${(pred.spatial_min_distance_m / 1000).toFixed(1)}km`}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Show More / Show Less */}
              {filteredPredictions.length > displayCount && (
                <button
                  onClick={() => setDisplayCount(filteredPredictions.length)}
                  className="w-full py-3 text-sm text-emerald-400 hover:text-emerald-300 hover:bg-emerald-900/20 border border-emerald-500/20 rounded-xl transition-colors mt-2"
                >
                  Show all {filteredPredictions.length} species ({filteredPredictions.length - displayCount} more)
                </button>
              )}
              {displayCount > 30 && filteredPredictions.length > 30 && (
                <button
                  onClick={() => setDisplayCount(30)}
                  className="w-full py-2 text-xs text-emerald-400/60 hover:text-emerald-300 transition-colors mt-1"
                >
                  Show fewer
                </button>
              )}

              <div className="pt-4 text-center border-t border-emerald-500/10">
                <p className="text-xs text-emerald-200/50 mb-3">
                  Multi-signal predictions: satellite embedding + spatial proximity + WCVP range + ecoregion + climate
                </p>
                <button
                  onClick={onClose}
                  className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors font-medium"
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {/* No Predictions */}
          {status === 'complete' && predictions.length === 0 && (
            <div className="py-8 text-center">
              <p className="text-emerald-200/70 mb-4">
                No species predictions available for this location
              </p>
              <button
                onClick={onClose}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          )}

          {/* Fallback - should never show but helps debugging */}
          {status !== 'sampling' && status !== 'predicting' && status !== 'error' && status !== 'complete' && (
            <div className="py-8 text-center">
              <div className="p-4 bg-yellow-900/30 border border-yellow-500/50 rounded-lg">
                <p className="text-yellow-300">Unknown status: {status}</p>
                <button
                  onClick={onClose}
                  className="mt-4 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Render using portal to document.body (outside Leaflet container)
  if (!mounted) return null;

  return createPortal(modalContent, document.body);
}
