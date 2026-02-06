'use client';

import { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X, Loader2, MapPin, Sparkles, Trees, AlertCircle, ChevronDown, Leaf, Globe, AlertTriangle } from 'lucide-react';
import Link from 'next/link';
import L from 'leaflet';
import { GeoJSONPolygon } from '@/lib/types';

interface PolygonPrediction {
  taxon_id: string;
  scientific_name: string;
  common_name: string | null;
  family: string;
  growth_form: string | null;
  avg_suitability: number;
  coverage_percent: number;
  coverage_points: number;
  total_points: number;
  score_range: {
    min: number;
    max: number;
    variability: number;
  };
  combined_score: number;
  native_status?: 'native' | 'introduced' | 'invasive' | 'native_and_introduced' | 'unknown';
  is_native?: boolean;
  is_introduced?: boolean;
  is_invasive?: boolean;
}

interface SamplePoint {
  lat: number;
  lng: number;
  elevation?: number;
}

interface LocationContext {
  ecoregions: {
    eco_id: number;
    eco_name: string;
    biome_name: string;
    realm: string;
    weight: number;
  }[];
  countries: string[];
}

interface NativeStatusSummary {
  native: number;
  introduced: number;
  invasive: number;
  native_and_introduced: number;
  unknown: number;
}

interface PolygonPredictionResponse {
  success: boolean;
  polygon_summary: {
    bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number };
    approx_area_km2: number;
    sample_strategy: string;
    sample_points_requested: number;
    sample_points_succeeded: number;
  };
  location_context?: LocationContext;
  sample_points: SamplePoint[];
  results: {
    species_count: number;
    native_status_summary?: NativeStatusSummary;
    predictions: PolygonPrediction[];
  };
}

interface PolygonPredictionModalProps {
  geometry: GeoJSONPolygon;
  onClose: () => void;
  map?: L.Map | null;
}

export default function PolygonPredictionModal({ geometry, onClose, map }: PolygonPredictionModalProps) {
  const [status, setStatus] = useState<'loading' | 'complete' | 'error'>('loading');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('Initializing...');
  const [predictions, setPredictions] = useState<PolygonPrediction[]>([]);
  const [polygonSummary, setPolygonSummary] = useState<PolygonPredictionResponse['polygon_summary'] | null>(null);
  const [locationContext, setLocationContext] = useState<LocationContext | null>(null);
  const [nativeStatusSummary, setNativeStatusSummary] = useState<NativeStatusSummary | null>(null);
  const [samplePoints, setSamplePoints] = useState<SamplePoint[]>([]);
  const [errorMessage, setErrorMessage] = useState('');
  const [mounted, setMounted] = useState(false);
  const [displayLimit, setDisplayLimit] = useState(50); // Show 50 initially for performance
  const modalRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  // Handle client-side mounting for portal
  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  // Disable map interactions when modal is open
  useEffect(() => {
    if (map) {
      map.scrollWheelZoom.disable();
      map.dragging.disable();
      map.touchZoom.disable();
      map.doubleClickZoom.disable();
      map.boxZoom.disable();
      map.keyboard.disable();
    }

    if (modalRef.current) {
      L.DomEvent.disableClickPropagation(modalRef.current);
      L.DomEvent.disableScrollPropagation(modalRef.current);
    }

    if (overlayRef.current) {
      L.DomEvent.disableClickPropagation(overlayRef.current);
      L.DomEvent.disableScrollPropagation(overlayRef.current);
    }

    document.body.style.overflow = 'hidden';

    return () => {
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
    console.log('Starting polygon prediction...');
    runPolygonPrediction();
  }, [geometry]);

  const runPolygonPrediction = async () => {
    try {
      setStatus('loading');
      setProgress(10);
      setMessage('Analyzing polygon area...');

      await new Promise(resolve => setTimeout(resolve, 200));

      setMessage('Generating sample points within polygon...');
      setProgress(20);

      await new Promise(resolve => setTimeout(resolve, 200));

      setMessage('Sampling AlphaEarth satellite data (this may take 30-60 seconds)...');
      setProgress(30);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth';

      const response = await fetch(`${apiUrl}/api/prediction/polygon`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          geometry,
          sample_count: 9,
          strategy: 'grid',
          min_similarity: 0.70  // 70% threshold - filters out marginal matches
        })
      });

      setProgress(80);
      setMessage('Processing predictions...');

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || errorData.error || `HTTP ${response.status}`);
      }

      const data: PolygonPredictionResponse = await response.json();

      if (!data.success) {
        throw new Error('Prediction request failed');
      }

      setPolygonSummary(data.polygon_summary);
      setLocationContext(data.location_context || null);
      setSamplePoints(data.sample_points);
      setPredictions(data.results.predictions);
      setNativeStatusSummary(data.results.native_status_summary || null);
      setProgress(100);
      setMessage('Complete!');
      setStatus('complete');

    } catch (error) {
      console.error('Polygon prediction error:', error);
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
        className="relative w-full max-w-4xl max-h-[90vh] bg-gradient-to-br from-emerald-950 to-black border border-emerald-500/30 shadow-2xl rounded-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex-shrink-0 bg-gradient-to-r from-emerald-900/90 to-emerald-800/90 backdrop-blur-md px-6 py-4 border-b border-emerald-500/20 rounded-t-2xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Trees className="h-6 w-6 text-emerald-300" />
              <div>
                <h2 className="text-xl font-semibold text-white">Area Species Prediction</h2>
                <p className="text-sm text-emerald-200">
                  <MapPin className="inline h-3 w-3 mr-1" />
                  Analyzing polygon ({polygonSummary?.approx_area_km2?.toFixed(1) || '...'} km²)
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
          {/* Loading State */}
          {status === 'loading' && (
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
                Sampling multiple points within your polygon to find species that thrive across the entire area...
              </p>
            </div>
          )}

          {/* Error State */}
          {status === 'error' && (
            <div className="py-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 mb-4">
                <AlertCircle className="h-8 w-8 text-red-400" />
              </div>
              <h3 className="text-lg font-medium text-white mb-2">Prediction Failed</h3>
              <p className="text-emerald-200/70 mb-4 max-w-md mx-auto">{errorMessage}</p>
              <button
                onClick={onClose}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          )}

          {/* Success State */}
          {status === 'complete' && predictions.length > 0 && (
            <div className="space-y-4">
              {/* Summary Banner */}
              <div className="bg-black/30 rounded-xl p-4 border border-emerald-500/20">
                <div className="flex items-center justify-between flex-wrap gap-4 mb-3">
                  <div>
                    <h3 className="text-lg font-medium text-white mb-1">
                      {predictions.length} Species Predicted for This Area
                    </h3>
                    <p className="text-sm text-emerald-200/70">
                      Based on {polygonSummary?.sample_points_succeeded} sample points across {polygonSummary?.approx_area_km2?.toFixed(1)} km²
                    </p>
                  </div>
                  <div className="flex gap-4 text-center">
                    <div className="bg-emerald-500/10 rounded-lg px-4 py-2">
                      <div className="text-xl font-bold text-emerald-400">
                        {polygonSummary?.sample_points_succeeded}
                      </div>
                      <div className="text-xs text-emerald-300/60">Sample Points</div>
                    </div>
                  </div>
                </div>

                {/* Location Context */}
                {locationContext && locationContext.ecoregions.length > 0 && (
                  <div className="mb-3 pt-3 border-t border-emerald-500/10">
                    <div className="flex items-center gap-2 mb-1">
                      <Globe className="h-4 w-4 text-emerald-400" />
                      <span className="text-sm font-medium text-white">
                        {locationContext.ecoregions.length === 1
                          ? locationContext.ecoregions[0].eco_name
                          : `${locationContext.ecoregions.length} Ecoregions`}
                      </span>
                    </div>
                    {locationContext.ecoregions.length === 1 && (
                      <p className="text-xs text-emerald-300/60 ml-6">
                        {locationContext.ecoregions[0].biome_name} • {locationContext.ecoregions[0].realm}
                      </p>
                    )}
                    {locationContext.countries.length > 0 && (
                      <p className="text-xs text-emerald-300/50 ml-6 mt-1">
                        {locationContext.countries.slice(0, 3).join(', ')}
                        {locationContext.countries.length > 3 && ` +${locationContext.countries.length - 3} more`}
                      </p>
                    )}
                  </div>
                )}

                {/* Native Status Summary */}
                {nativeStatusSummary && (
                  <div className="flex flex-wrap gap-2 pt-3 border-t border-emerald-500/10">
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
                    {nativeStatusSummary.native_and_introduced > 0 && (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-yellow-500/20 text-yellow-300 text-xs">
                        {nativeStatusSummary.native_and_introduced} Native+Intro
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

              {/* Predictions List */}
              <div className="space-y-3">
                {predictions.slice(0, displayLimit).map((pred, index) => (
                  <Link
                    key={`${pred.taxon_id}-${index}`}
                    href={`/species/${pred.taxon_id}`}
                    className="block bg-black/30 backdrop-blur-sm border border-emerald-500/20 rounded-xl p-4 hover:border-emerald-400/40 hover:bg-black/40 transition-all"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-bold">
                            {index + 1}
                          </span>
                          <h4 className="text-white font-medium italic">
                            {pred.scientific_name}
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
                        </div>
                        <p className="text-sm text-emerald-300/70 ml-8">
                          {pred.family}
                          {pred.common_name && ` • ${pred.common_name}`}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-emerald-400">
                          {pred.avg_suitability}%
                        </div>
                        <div className="text-xs text-emerald-300/50">avg suitability</div>
                      </div>
                    </div>

                    {/* Suitability Bar */}
                    <div className="h-1.5 bg-emerald-950/50 rounded-full overflow-hidden mb-3">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-emerald-300"
                        style={{ width: `${pred.avg_suitability}%` }}
                      />
                    </div>

                    {/* Coverage and Variability */}
                    <div className="flex items-center justify-between text-xs text-emerald-200/50">
                      <span className="flex items-center gap-3">
                        <span>
                          Coverage: {pred.coverage_points}/{pred.total_points} points ({pred.coverage_percent}%)
                        </span>
                        {pred.growth_form && (
                          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300/70">
                            {pred.growth_form}
                          </span>
                        )}
                      </span>
                      <span>
                        Range: {pred.score_range.min}%-{pred.score_range.max}%
                        {pred.score_range.variability > 20 && (
                          <span className="ml-1 text-yellow-400/70">(variable)</span>
                        )}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>

              {/* Show More Button */}
              {predictions.length > displayLimit && (
                <div className="pt-4 text-center">
                  <button
                    onClick={() => setDisplayLimit(prev => prev + 100)}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 rounded-lg transition-colors text-sm"
                  >
                    <ChevronDown className="w-4 h-4" />
                    Show More ({predictions.length - displayLimit} remaining)
                  </button>
                </div>
              )}

              {/* Footer */}
              <div className="pt-4 text-center border-t border-emerald-500/10">
                <p className="text-xs text-emerald-200/50 mb-3">
                  Showing {Math.min(displayLimit, predictions.length)} of {predictions.length} species • Ranked by suitability and coverage
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
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-yellow-500/10 mb-4">
                <Sparkles className="h-8 w-8 text-yellow-400" />
              </div>
              <h3 className="text-lg font-medium text-white mb-2">No Predictions Available</h3>
              <p className="text-emerald-200/70 mb-4">
                No species predictions found for this area. The region may have limited satellite coverage.
              </p>
              <button
                onClick={onClose}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  if (!mounted) return null;

  return createPortal(modalContent, document.body);
}
