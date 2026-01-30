'use client';

import { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X, Loader2, MapPin, Sparkles, Leaf, AlertTriangle, Globe } from 'lucide-react';
import Link from 'next/link';
import { getTopCommonNames } from '@/utils/commonNames';
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
  taxon_id: string;
  taxon_full?: string;
  species_scientific_name?: string;
  family: string;
  common_name: string | null;
  cluster_id: number;
  cluster_size: number;
  total_occurrences: number;
  representative_lat: number;
  representative_lon: number;
  similarity_score: string;
  confidence: number;
  habitat_count?: number;
  alternate_habitats?: AlternateHabitat[];
  native_status?: 'native' | 'introduced' | 'invasive' | 'native_and_introduced' | 'unknown';
  is_native?: boolean;
  is_introduced?: boolean;
  is_invasive?: boolean;
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

interface NativeStatusSummary {
  native: number;
  introduced: number;
  invasive: number;
  native_and_introduced: number;
  unknown: number;
}

interface PredictionResponse {
  success: boolean;
  prediction_count: number;
  predictions: SpeciesPrediction[];
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
  const [mounted, setMounted] = useState(false);
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

    sampleAndPredict();
  }, [lat, lon]);

  const sampleAndPredict = async () => {
    try {
      // Step 1: Start with immediate UI feedback
      setMessage('Initializing Google Earth Engine connection...');
      setProgress(5);
      setStatus('sampling');

      // Force render by yielding to event loop
      await new Promise(resolve => setTimeout(resolve, 100));

      setMessage('Requesting AlphaEarth satellite data...');
      setProgress(15);
      await new Promise(resolve => setTimeout(resolve, 100));

      setMessage('Earth Engine processing location (this may take 10-30 seconds)...');
      setProgress(20);

      console.log('📡 Fetching from GEE service...');
      const fetchStartTime = Date.now();

      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth';
      const response = await fetch(`${apiBase}/api/prediction/sample?lat=${lat}&lon=${lon}`);

      const fetchDuration = ((Date.now() - fetchStartTime) / 1000).toFixed(1);
      console.log(`✅ GEE fetch completed in ${fetchDuration}s`);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || error.details || 'Failed to sample location');
      }

      setMessage('Extracting 64-dimensional habitat embedding...');
      setProgress(60);

      const samplingResult = await response.json();
      console.log('📊 Embedding received:', samplingResult.data_source);

      if (!samplingResult.success || !samplingResult.embedding) {
        // Check if it's a no-coverage error (from multi-year service)
        if (samplingResult.details?.years_tried) {
          const detailsMsg = samplingResult.details.message ||
            'This location may be over water, in an urban area, or outside satellite coverage.';
          const yearsMsg = `Tried years: ${samplingResult.details.years_tried.join(', ')}`;
          throw new Error(`No AlphaEarth data available. ${detailsMsg} (${yearsMsg})`);
        } else {
          throw new Error(samplingResult.error || 'No AlphaEarth data at this location');
        }
      }

      // Check if using demo mode
      if (samplingResult.demo_mode) {
        setIsDemoMode(true);
      }

      setMessage('Analyzing 64-dimensional habitat signature...');
      setProgress(65);
      await new Promise(resolve => setTimeout(resolve, 100));

      // Step 2: Predict species from embedding
      setStatus('predicting');
      setMessage('Querying species database (500 habitat centroids)...');
      setProgress(75);

      // CRITICAL: Wait to ensure React re-renders before fast API call
      await new Promise(resolve => setTimeout(resolve, 300));

      console.log('🔍 Searching for similar species...');
      const predictionStartTime = Date.now();

      const predictionResponse = await fetch(`${apiBase}/api/prediction/from-embedding`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          embedding: samplingResult.embedding,
          limit: 10,
          lat,
          lon
        })
      });

      console.log(`✅ Prediction completed in ${Date.now() - predictionStartTime}ms`);

      if (!predictionResponse.ok) {
        const errorText = await predictionResponse.text();
        throw new Error(`Failed to predict species: ${predictionResponse.status} ${errorText}`);
      }

      const predictionData: PredictionResponse = await predictionResponse.json();
      console.log(`✅ Received ${predictionData.prediction_count} species predictions`);

      setMessage('Species predictions ready!');
      setProgress(100);
      setPredictions(predictionData.predictions);
      setLocationContext(predictionData.location_context || null);
      setNativeStatusSummary(predictionData.native_status_summary || null);
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
                  Based on satellite habitat signature similarity
                </p>
                {isDemoMode && (
                  <div className="mt-3 px-3 py-2 bg-yellow-900/30 border border-yellow-600/50 rounded-lg inline-block">
                    <span className="text-xs text-yellow-400">
                      🔬 DEMO MODE: Using simulated data for testing
                    </span>
                  </div>
                )}
              </div>

              {/* Location Context & Native Status Summary */}
              {(locationContext || nativeStatusSummary) && (
                <div className="bg-black/30 rounded-xl p-4 border border-emerald-500/20 mb-4">
                  {locationContext && (
                    <div className="mb-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Globe className="h-4 w-4 text-emerald-400" />
                        <span className="text-sm font-medium text-white">{locationContext.ecoregion.eco_name}</span>
                      </div>
                      <p className="text-xs text-emerald-300/60 ml-6">
                        {locationContext.ecoregion.biome_name} • {locationContext.ecoregion.realm}
                        {locationContext.countries.length > 0 && ` • ${locationContext.countries.join(', ')}`}
                      </p>
                    </div>
                  )}
                  {nativeStatusSummary && (
                    <div className="flex flex-wrap gap-2">
                      {nativeStatusSummary.native > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-green-500/20 text-green-300 text-xs">
                          <Leaf className="h-3 w-3" />
                          {nativeStatusSummary.native} Native
                        </span>
                      )}
                      {nativeStatusSummary.introduced > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-blue-500/20 text-blue-300 text-xs">
                          <Globe className="h-3 w-3" />
                          {nativeStatusSummary.introduced} Introduced
                        </span>
                      )}
                      {nativeStatusSummary.invasive > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-red-500/20 text-red-300 text-xs">
                          <AlertTriangle className="h-3 w-3" />
                          {nativeStatusSummary.invasive} Invasive
                        </span>
                      )}
                      {nativeStatusSummary.unknown > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-gray-500/20 text-gray-300 text-xs">
                          {nativeStatusSummary.unknown} Unknown
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-3">
                {predictions.map((pred, index) => {
                  const isExpanded = expandedSpecies.has(pred.taxon_id);
                  const hasAlternateHabitats = pred.alternate_habitats && pred.alternate_habitats.length > 0;

                  return (
                    <div key={`${pred.taxon_id}-${index}`} className="bg-black/30 backdrop-blur-sm border border-emerald-500/20 rounded-xl hover:border-emerald-400/40 transition-all">
                      <Link href={`/species/${pred.taxon_id}`} className="block p-4 hover:bg-black/40 transition-all cursor-pointer">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-bold flex-shrink-0">
                              {index + 1}
                            </span>
                            <div className="min-w-0">
                              <h4 className="text-white font-medium italic truncate">
                                {pred.taxon_full || pred.species_scientific_name}
                              </h4>
                              {pred.common_name && (
                                <p className="text-sm text-emerald-300/70 truncate">
                                  {getTopCommonNames(pred.common_name, 3, 80)}
                                </p>
                              )}
                            </div>
                          </div>
                          <div className="text-right flex-shrink-0 ml-3">
                            <div className="text-lg font-bold text-emerald-400">
                              {(pred.confidence * 100).toFixed(0)}%
                            </div>
                            <div className="text-xs text-emerald-300/50">
                              {pred.habitat_count && pred.habitat_count > 1 ? `${pred.habitat_count} habitats` : 'confidence'}
                            </div>
                          </div>
                        </div>

                        {/* Confidence Bar */}
                        <div className="h-1.5 bg-emerald-950/50 rounded-full overflow-hidden ml-8">
                          <div
                            className="h-full bg-gradient-to-r from-emerald-500 to-emerald-300 transition-all duration-300"
                            style={{ width: `${pred.confidence * 100}%` }}
                          />
                        </div>
                      </Link>

                      {/* Expandable Habitat Breakdown */}
                      {hasAlternateHabitats && (
                        <>
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              toggleExpanded(pred.taxon_id);
                            }}
                            onMouseDown={(e) => {
                              e.stopPropagation();
                            }}
                            onMouseUp={(e) => {
                              e.stopPropagation();
                            }}
                            className="w-full px-4 py-2 text-xs text-emerald-400 hover:text-emerald-300 border-t border-emerald-500/10 hover:bg-black/20 transition-colors"
                          >
                            {isExpanded ? '▼' : '▶'} {pred.habitat_count} habitat distribution
                          </button>

                          {isExpanded && (
                            <div className="px-4 pb-4 space-y-2 border-t border-emerald-500/10">
                              {/* Primary Habitat */}
                              <div className="pt-3 text-xs">
                                <div className="flex justify-between items-center mb-1">
                                  <span className="text-emerald-400 font-medium">Primary habitat:</span>
                                  <span className="text-emerald-300">{(pred.confidence * 100).toFixed(1)}% match</span>
                                </div>
                                <div className="text-emerald-200/50">
                                  {pred.cluster_size} occurrences at ({pred.representative_lat.toFixed(2)}, {pred.representative_lon.toFixed(2)})
                                </div>
                              </div>

                              {/* Alternate Habitats */}
                              {pred.alternate_habitats!.map((habitat, idx) => (
                                <div key={idx} className="text-xs">
                                  <div className="flex justify-between items-center mb-1">
                                    <span className="text-emerald-400/70 font-medium">Habitat {idx + 2}:</span>
                                    <span className="text-emerald-300/70">{(habitat.confidence * 100).toFixed(1)}% match</span>
                                  </div>
                                  <div className="text-emerald-200/40">
                                    {habitat.cluster_size} occurrences at ({habitat.representative_lat.toFixed(2)}, {habitat.representative_lon.toFixed(2)})
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="pt-4 text-center border-t border-emerald-500/10">
                <p className="text-xs text-emerald-200/50 mb-3">
                  Predictions based on AlphaEarth 64-D satellite embeddings
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
