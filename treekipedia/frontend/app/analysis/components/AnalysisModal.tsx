'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  X, Loader2, ChevronLeft, MapPin, Trees, Sparkles, Leaf,
  AlertCircle, Search, TreePine, Sprout, Droplets, Wind, Bug
} from 'lucide-react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import L from 'leaflet';
import {
  AOIDefinition, AnalysisPhase, RecommendationStrategy,
  PlotAnalysisResponse, SpeciesResearchStatus, BulkResearchStatusResponse
} from '@/lib/types';
import {
  predictPolygonSpecies, checkBulkResearchStatus, triggerResearch
} from '@/lib/api';
import { useCredits } from '@/hooks/useCredits';
import { CreditGate } from '@/components/CreditGate';
import CrossAnalysisSummary from './CrossAnalysisSummary';

// ============================================
// Inline Types (from PolygonPredictionModal pattern)
// ============================================

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
  score_range: { min: number; max: number; variability: number };
  combined_score: number;
  native_status?: 'native' | 'introduced' | 'invasive' | 'native_and_introduced' | 'unknown';
  is_native?: boolean;
  is_introduced?: boolean;
  is_invasive?: boolean;
  leaf_score?: number;
  leaf_tier?: 'BEST' | 'GOOD' | 'ACCEPTABLE' | 'LOW';
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

interface PredictionResponse {
  success: boolean;
  polygon_summary: {
    bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number };
    approx_area_km2: number;
    sample_strategy: string;
    sample_points_requested: number;
    sample_points_succeeded: number;
  };
  location_context?: LocationContext;
  sample_points: { lat: number; lng: number; elevation?: number }[];
  results: {
    species_count: number;
    native_status_summary?: Record<string, number>;
    predictions: PolygonPrediction[];
  };
}

// ============================================
// Strategy definitions
// ============================================

const STRATEGIES: { key: RecommendationStrategy; label: string; desc: string; icon: React.ReactNode }[] = [
  { key: 'general', label: 'General Restoration', desc: 'Balanced species mix for ecosystem health', icon: <Trees className="h-5 w-5" /> },
  { key: 'rewilding', label: 'Rewilding', desc: 'Native species for ecological recovery', icon: <TreePine className="h-5 w-5" /> },
  { key: 'agroforestry', label: 'Agroforestry', desc: 'Species with productive value', icon: <Sprout className="h-5 w-5" /> },
  { key: 'riparian', label: 'Riparian', desc: 'Waterway buffer zone species', icon: <Droplets className="h-5 w-5" /> },
  { key: 'carbon', label: 'Carbon Sequestration', desc: 'Maximum carbon capture potential', icon: <Wind className="h-5 w-5" /> },
  { key: 'biodiversity', label: 'Biodiversity', desc: 'Maximize species diversity', icon: <Bug className="h-5 w-5" /> },
];

// ============================================
// Props
// ============================================

interface AnalysisModalProps {
  aoi: AOIDefinition;
  initialSummary: PlotAnalysisResponse;
  onClose: () => void;
  map?: L.Map | null;
}

// ============================================
// Component
// ============================================

export default function AnalysisModal({ aoi, initialSummary, onClose, map }: AnalysisModalProps) {
  const router = useRouter();
  const { data: session, status: authStatus } = useSession();
  const { balance, refreshBalance, isAuthenticated } = useCredits();
  const isAuth = authStatus === 'authenticated';

  // Phase & navigation
  const [phase, setPhase] = useState<AnalysisPhase>('summary');
  const [phaseHistory, setPhaseHistory] = useState<AnalysisPhase[]>([]);

  // Loading states
  const [loadingStatus, setLoadingStatus] = useState<'idle' | 'loading' | 'complete' | 'error'>('idle');
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  // Credit gate
  const [showCreditGate, setShowCreditGate] = useState(false);
  const [creditGateCost, setCreditGateCost] = useState(0);
  const [creditGateLabel, setCreditGateLabel] = useState('');
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);

  // Prediction data (cached)
  const [predictionData, setPredictionData] = useState<PredictionResponse | null>(null);
  const [locationContext, setLocationContext] = useState<LocationContext | null>(null);

  // Recommendation data (cached)
  const [recommendationData, setRecommendationData] = useState<PredictionResponse | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<RecommendationStrategy | null>(null);

  // Research status
  const [researchStatuses, setResearchStatuses] = useState<BulkResearchStatusResponse>({});

  // Research phase
  const [researchProgress, setResearchProgress] = useState(0);
  const [researchTotal, setResearchTotal] = useState(0);
  const [researchingTaxonId, setResearchingTaxonId] = useState<string | null>(null);

  // Display
  const [displayLimit, setDisplayLimit] = useState(50);

  // Portal mount
  const [mounted, setMounted] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  // Disable map interactions
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

  // Escape key handler
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  // ============================================
  // Navigation helpers
  // ============================================

  const navigateTo = useCallback((nextPhase: AnalysisPhase) => {
    setPhaseHistory(prev => [...prev, phase]);
    setPhase(nextPhase);
    setShowCreditGate(false);
    setLoadingStatus('idle');
    setErrorMessage('');
  }, [phase]);

  const goBack = useCallback(() => {
    if (phaseHistory.length > 0) {
      const prev = phaseHistory[phaseHistory.length - 1];
      setPhaseHistory(h => h.slice(0, -1));
      setPhase(prev);
      setShowCreditGate(false);
      setLoadingStatus('idle');
      setErrorMessage('');
    }
  }, [phaseHistory]);

  // ============================================
  // Auth + credit gate helper
  // ============================================

  const requireAuthAndCredits = useCallback((cost: number, label: string, action: () => void) => {
    if (!isAuth) {
      router.push('/login');
      return;
    }
    setCreditGateCost(cost);
    setCreditGateLabel(label);
    setPendingAction(() => action);
    setShowCreditGate(true);
  }, [isAuth, router]);

  // ============================================
  // Prediction action
  // ============================================

  const runPrediction = useCallback(async () => {
    setShowCreditGate(false);
    navigateTo('prediction');
    setLoadingStatus('loading');
    setProgress(10);
    setStatusMessage('Sampling AlphaEarth satellite data...');

    try {
      setProgress(30);
      setStatusMessage('Processing habitat embeddings (30-60 seconds)...');

      const data = await predictPolygonSpecies(aoi.geometry, 9);

      setProgress(80);
      setStatusMessage('Building species list...');

      setPredictionData(data);
      setLocationContext(data.location_context || null);
      setProgress(100);
      setLoadingStatus('complete');

      // Load research statuses async
      if (data.results?.predictions?.length > 0) {
        const ids = data.results.predictions.map((p: PolygonPrediction) => p.taxon_id);
        try {
          const statuses = await checkBulkResearchStatus(ids);
          setResearchStatuses(prev => ({ ...prev, ...statuses }));
        } catch (e) {
          console.error('Failed to load research statuses:', e);
        }
      }
    } catch (error) {
      console.error('Prediction error:', error);
      setErrorMessage(error instanceof Error ? error.message : 'Prediction failed');
      setLoadingStatus('error');
    }
  }, [aoi.geometry, navigateTo]);

  // ============================================
  // Recommendation action
  // ============================================

  const runRecommendation = useCallback(async (strategy: RecommendationStrategy) => {
    setShowCreditGate(false);
    setSelectedStrategy(strategy);
    navigateTo('recommendation');
    setLoadingStatus('loading');
    setProgress(10);
    setStatusMessage('Running LEAF ecological scoring...');

    try {
      setProgress(30);
      setStatusMessage('Analyzing species suitability (30-60 seconds)...');

      const data = await predictPolygonSpecies(aoi.geometry, 9);

      setProgress(80);
      setStatusMessage('Ranking by restoration strategy...');

      setRecommendationData(data);
      setLocationContext(data.location_context || null);
      setProgress(100);
      setLoadingStatus('complete');

      // Load research statuses async
      if (data.results?.predictions?.length > 0) {
        const ids = data.results.predictions.map((p: PolygonPrediction) => p.taxon_id);
        try {
          const statuses = await checkBulkResearchStatus(ids);
          setResearchStatuses(prev => ({ ...prev, ...statuses }));
        } catch (e) {
          console.error('Failed to load research statuses:', e);
        }
      }
    } catch (error) {
      console.error('Recommendation error:', error);
      setErrorMessage(error instanceof Error ? error.message : 'Recommendation failed');
      setLoadingStatus('error');
    }
  }, [aoi.geometry, navigateTo]);

  // ============================================
  // Research action
  // ============================================

  const runResearch = useCallback(async () => {
    setShowCreditGate(false);
    navigateTo('research');
    setLoadingStatus('loading');

    // Get unresearched species from whichever result set is active
    const activeResults = predictionData?.results?.predictions || recommendationData?.results?.predictions || [];
    const unresearched = activeResults.filter(
      (p: PolygonPrediction) => researchStatuses[p.taxon_id] === 'unresearched'
    );

    setResearchTotal(unresearched.length);
    setResearchProgress(0);

    try {
      for (let i = 0; i < unresearched.length; i++) {
        const species = unresearched[i];
        setResearchingTaxonId(species.taxon_id);
        setStatusMessage(`Researching ${species.scientific_name} (${i + 1}/${unresearched.length})...`);
        setProgress(Math.round(((i + 1) / unresearched.length) * 100));
        setResearchProgress(i + 1);

        try {
          await triggerResearch(species.taxon_id, false);
          setResearchStatuses(prev => ({ ...prev, [species.taxon_id]: 'researched' }));
        } catch (err) {
          console.error(`Failed to research ${species.taxon_id}:`, err);
          // Continue with remaining species
        }
      }

      setLoadingStatus('complete');
      setStatusMessage('Research complete!');
      await refreshBalance();
    } catch (error) {
      console.error('Research error:', error);
      setErrorMessage(error instanceof Error ? error.message : 'Research failed');
      setLoadingStatus('error');
    }
  }, [predictionData, recommendationData, researchStatuses, navigateTo, refreshBalance]);

  // ============================================
  // Research status dot helper
  // ============================================

  const ResearchDot = ({ taxonId }: { taxonId: string }) => {
    const status = researchStatuses[taxonId];
    if (!status) return <div className="w-2.5 h-2.5 rounded-full bg-gray-500" title="Unknown" />;
    const colors = {
      researched: 'bg-green-400',
      partial: 'bg-yellow-400',
      unresearched: 'bg-gray-500',
    };
    const labels = {
      researched: 'Researched',
      partial: 'Partially researched',
      unresearched: 'Not researched',
    };
    return <div className={`w-2.5 h-2.5 rounded-full ${colors[status]}`} title={labels[status]} />;
  };

  // ============================================
  // Native status badge (from PolygonPredictionModal)
  // ============================================

  const NativeBadge = ({ prediction }: { prediction: PolygonPrediction }) => {
    if (prediction.is_native) return <span className="text-xs px-1.5 py-0.5 rounded bg-green-500/20 text-green-300 border border-green-500/30">Native</span>;
    if (prediction.is_invasive) return <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30">Invasive</span>;
    if (prediction.is_introduced) return <span className="text-xs px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-300 border border-orange-500/30">Introduced</span>;
    return null;
  };

  // ============================================
  // Species list renderer (shared between prediction + recommendation)
  // ============================================

  const renderSpeciesList = (predictions: PolygonPrediction[]) => {
    const displayed = predictions.slice(0, displayLimit);
    const unresearchedCount = predictions.filter(p => researchStatuses[p.taxon_id] === 'unresearched').length;
    const researchCost = unresearchedCount * 25;

    return (
      <div className="space-y-3">
        {/* Stats bar */}
        <div className="flex items-center justify-between text-sm text-white/60 px-1">
          <span>{predictions.length} species found</span>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-green-400" /> Researched</span>
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-yellow-400" /> Partial</span>
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-gray-500" /> None</span>
          </div>
        </div>

        {/* Species cards */}
        {displayed.map((pred, idx) => (
          <Link
            key={pred.taxon_id}
            href={`/species/${pred.taxon_id}`}
            target="_blank"
            className="block bg-black/30 border border-white/10 rounded-lg p-3 hover:border-emerald-500/40 transition-colors"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <ResearchDot taxonId={pred.taxon_id} />
                <div className="min-w-0">
                  <div className="text-white font-medium text-sm truncate">
                    {pred.common_name || pred.scientific_name}
                  </div>
                  <div className="text-white/50 text-xs italic truncate">
                    {pred.scientific_name}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <NativeBadge prediction={pred} />
                <div className="text-right">
                  <div className="text-emerald-400 font-semibold text-sm">
                    {Math.round(pred.avg_suitability * 100)}%
                  </div>
                  <div className="text-white/40 text-xs">suitability</div>
                </div>
              </div>
            </div>
            {/* Suitability bar */}
            <div className="mt-2 bg-black/40 rounded-full h-1.5 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400"
                style={{ width: `${Math.round(pred.avg_suitability * 100)}%` }}
              />
            </div>
          </Link>
        ))}

        {/* Show more */}
        {predictions.length > displayLimit && (
          <button
            onClick={() => setDisplayLimit(prev => prev + 50)}
            className="w-full py-2 text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            Show more ({predictions.length - displayLimit} remaining)
          </button>
        )}

        {/* Research CTA */}
        {unresearchedCount > 0 && isAuth && (
          <div className="mt-4 p-4 bg-emerald-900/20 border border-emerald-600/30 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-white text-sm font-medium">
                {unresearchedCount} species not yet researched
              </span>
              <span className="text-amber-400 text-sm">
                {researchCost} credits
              </span>
            </div>
            <button
              onClick={() => requireAuthAndCredits(researchCost, 'Research Remaining Species', runResearch)}
              className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Research Remaining & Generate Guide
            </button>
          </div>
        )}
      </div>
    );
  };

  // ============================================
  // Render phases
  // ============================================

  const renderSummaryPhase = () => (
    <div className="space-y-4">
      {/* AOI info */}
      <div className="flex items-center gap-2 text-white/60 text-sm">
        <MapPin className="h-4 w-4" />
        <span>
          {aoi.type === 'polygon' ? 'Drawn polygon' :
           aoi.type === 'point' ? 'Point buffer (~1 km)' :
           aoi.label || 'Uploaded KML'}
        </span>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-emerald-900/20 border border-emerald-600/30 rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-emerald-400">{initialSummary.totalSpecies}</div>
          <div className="text-sm text-white/60">Species Found</div>
        </div>
        <div className="bg-emerald-900/20 border border-emerald-600/30 rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-emerald-400">{initialSummary.totalOccurrences.toLocaleString()}</div>
          <div className="text-sm text-white/60">Total Occurrences</div>
        </div>
      </div>

      {/* Cross analysis */}
      {initialSummary.crossAnalysis && (
        <CrossAnalysisSummary
          crossAnalysis={initialSummary.crossAnalysis}
          totalSpecies={initialSummary.totalSpecies}
        />
      )}

      {/* CTA buttons */}
      <div className="grid grid-cols-2 gap-3 mt-6">
        <button
          onClick={() => requireAuthAndCredits(25, 'Species Prediction (AlphaEarth)', runPrediction)}
          className="flex flex-col items-center gap-2 p-4 bg-blue-900/20 border border-blue-600/30 rounded-lg hover:border-blue-400/50 transition-colors group"
        >
          <Sparkles className="h-6 w-6 text-blue-400 group-hover:text-blue-300" />
          <span className="text-white font-medium text-sm">Species Prediction</span>
          <span className="text-white/40 text-xs">AlphaEarth satellite analysis</span>
          <span className="text-amber-400 text-xs">25 credits</span>
        </button>
        <button
          onClick={() => navigateTo('recommendation')}
          className="flex flex-col items-center gap-2 p-4 bg-green-900/20 border border-green-600/30 rounded-lg hover:border-green-400/50 transition-colors group"
        >
          <Leaf className="h-6 w-6 text-green-400 group-hover:text-green-300" />
          <span className="text-white font-medium text-sm">Species Recommendation</span>
          <span className="text-white/40 text-xs">LEAF ecological scoring</span>
          <span className="text-amber-400 text-xs">25 credits</span>
        </button>
      </div>

      {/* Occurrence species list (free) */}
      {initialSummary.species.length > 0 && (
        <div className="mt-4">
          <h3 className="text-white/70 text-sm font-medium mb-2">Occurrence-Based Species ({initialSummary.species.length})</h3>
          <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
            {initialSummary.species.slice(0, 20).map(sp => (
              <Link
                key={sp.taxon_id}
                href={`/species/${sp.taxon_id}`}
                target="_blank"
                className="block bg-black/20 border border-white/5 rounded-lg p-2 hover:border-emerald-500/30 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <div className="text-white text-sm truncate">
                      {sp.common_name || sp.scientific_name}
                    </div>
                    <div className="text-white/40 text-xs italic truncate">{sp.scientific_name}</div>
                  </div>
                  <div className="text-right shrink-0 ml-2">
                    <div className="text-emerald-400 text-sm font-medium">{sp.occurrences}</div>
                    <div className="text-white/30 text-xs">occurrences</div>
                  </div>
                </div>
              </Link>
            ))}
            {initialSummary.species.length > 20 && (
              <div className="text-center text-white/40 text-xs py-1">
                + {initialSummary.species.length - 20} more species
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );

  const renderPredictionPhase = () => {
    if (loadingStatus === 'loading') return renderLoadingState();
    if (loadingStatus === 'error') return renderErrorState();
    if (!predictionData) return null;

    return (
      <div className="space-y-4">
        {/* Location context */}
        {locationContext && locationContext.ecoregions.length > 0 && (
          <div className="bg-black/30 border border-white/10 rounded-lg p-3">
            <div className="text-white/60 text-xs mb-1">Ecoregion Context</div>
            {locationContext.ecoregions.slice(0, 3).map(eco => (
              <div key={eco.eco_id} className="text-white text-sm">
                {eco.eco_name} <span className="text-white/40">({eco.biome_name})</span>
              </div>
            ))}
            {locationContext.countries.length > 0 && (
              <div className="text-white/40 text-xs mt-1">
                {locationContext.countries.join(', ')}
              </div>
            )}
          </div>
        )}

        {/* Polygon summary */}
        {predictionData.polygon_summary && (
          <div className="flex items-center gap-4 text-sm text-white/60">
            <span>{predictionData.polygon_summary.approx_area_km2.toFixed(1)} km²</span>
            <span>{predictionData.polygon_summary.sample_points_succeeded} sample points</span>
            <span>{predictionData.results.species_count} species</span>
          </div>
        )}

        {renderSpeciesList(predictionData.results.predictions)}
      </div>
    );
  };

  const renderRecommendationPhase = () => {
    // If no strategy selected yet, show picker
    if (!selectedStrategy && loadingStatus === 'idle') {
      return (
        <div className="space-y-4">
          <p className="text-white/60 text-sm">Choose a restoration strategy to get species recommendations tailored to your goals.</p>
          <div className="grid grid-cols-2 gap-3">
            {STRATEGIES.map(s => (
              <button
                key={s.key}
                onClick={() => requireAuthAndCredits(25, `${s.label} Recommendation`, () => runRecommendation(s.key))}
                className="flex flex-col items-center gap-2 p-4 bg-black/30 border border-white/10 rounded-lg hover:border-emerald-500/40 transition-colors text-center group"
              >
                <div className="text-emerald-400 group-hover:text-emerald-300">{s.icon}</div>
                <span className="text-white text-sm font-medium">{s.label}</span>
                <span className="text-white/40 text-xs">{s.desc}</span>
              </button>
            ))}
          </div>
          <div className="text-center text-amber-400 text-xs">25 credits per recommendation</div>
        </div>
      );
    }

    if (loadingStatus === 'loading') return renderLoadingState();
    if (loadingStatus === 'error') return renderErrorState();
    if (!recommendationData) return null;

    return (
      <div className="space-y-4">
        {/* Strategy badge */}
        {selectedStrategy && (
          <div className="flex items-center gap-2 text-white/60 text-sm">
            <Leaf className="h-4 w-4 text-emerald-400" />
            <span>Strategy: {STRATEGIES.find(s => s.key === selectedStrategy)?.label}</span>
          </div>
        )}

        {/* Location context */}
        {locationContext && locationContext.ecoregions.length > 0 && (
          <div className="bg-black/30 border border-white/10 rounded-lg p-3">
            <div className="text-white/60 text-xs mb-1">Ecoregion Context</div>
            {locationContext.ecoregions.slice(0, 3).map(eco => (
              <div key={eco.eco_id} className="text-white text-sm">
                {eco.eco_name} <span className="text-white/40">({eco.biome_name})</span>
              </div>
            ))}
          </div>
        )}

        {renderSpeciesList(recommendationData.results.predictions)}
      </div>
    );
  };

  const renderResearchPhase = () => {
    if (loadingStatus === 'loading') {
      return (
        <div className="space-y-4">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin text-emerald-400 mx-auto mb-3" />
            <div className="text-white font-medium">{statusMessage}</div>
            <div className="text-white/50 text-sm mt-1">
              {researchProgress} / {researchTotal} species
            </div>
          </div>
          <div className="bg-black/40 rounded-full h-3 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          {researchingTaxonId && (
            <div className="text-center text-white/40 text-xs">
              Current: {researchingTaxonId}
            </div>
          )}
        </div>
      );
    }

    if (loadingStatus === 'error') return renderErrorState();

    if (loadingStatus === 'complete') {
      return (
        <div className="space-y-4 text-center">
          <div className="text-emerald-400 text-5xl mb-2">&#10003;</div>
          <h3 className="text-white text-lg font-semibold">Research Complete</h3>
          <p className="text-white/60 text-sm">
            {researchTotal} species have been researched. Research data is now available on each species page.
          </p>
          <button
            onClick={() => {
              // Go back to whichever result view was active
              if (phaseHistory.includes('prediction')) {
                setPhase('prediction');
              } else if (phaseHistory.includes('recommendation')) {
                setPhase('recommendation');
              } else {
                setPhase('summary');
              }
              setPhaseHistory([]);
              setLoadingStatus('idle');
            }}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            Back to Results
          </button>
        </div>
      );
    }

    return null;
  };

  // ============================================
  // Shared render helpers
  // ============================================

  const renderLoadingState = () => (
    <div className="space-y-4 py-8">
      <div className="text-center">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-400 mx-auto mb-3" />
        <div className="text-white font-medium">{statusMessage}</div>
      </div>
      <div className="bg-black/40 rounded-full h-3 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );

  const renderErrorState = () => (
    <div className="py-8 text-center space-y-3">
      <AlertCircle className="h-8 w-8 text-red-400 mx-auto" />
      <div className="text-red-300 font-medium">Something went wrong</div>
      <div className="text-white/50 text-sm">{errorMessage}</div>
      <button
        onClick={goBack}
        className="px-4 py-2 bg-white/10 hover:bg-white/15 text-white rounded-lg text-sm transition-colors"
      >
        Go Back
      </button>
    </div>
  );

  // ============================================
  // Phase titles
  // ============================================

  const phaseTitle: Record<AnalysisPhase, string> = {
    summary: 'Site Analysis',
    prediction: 'Species Prediction',
    recommendation: 'Species Recommendation',
    research: 'Species Research',
  };

  // ============================================
  // Render
  // ============================================

  if (!mounted) return null;

  const modalContent = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[9999] flex items-center justify-center"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        ref={modalRef}
        className="relative w-full max-w-2xl max-h-[85vh] mx-4 bg-gray-900/95 backdrop-blur-xl border border-emerald-600/30 rounded-2xl shadow-2xl flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            {phaseHistory.length > 0 && (
              <button
                onClick={goBack}
                className="text-white/50 hover:text-white transition-colors"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
            )}
            <Trees className="h-5 w-5 text-emerald-400" />
            <h2 className="text-white font-semibold text-lg">{phaseTitle[phase]}</h2>
          </div>
          <button
            onClick={onClose}
            className="text-white/40 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* Credit gate overlay */}
          {showCreditGate && (
            <div className="mb-4">
              <CreditGate
                cost={creditGateCost}
                productLabel={creditGateLabel}
                balance={balance}
                onConfirm={() => {
                  if (pendingAction) pendingAction();
                }}
                onCancel={() => setShowCreditGate(false)}
              />
            </div>
          )}

          {/* Phase content */}
          {!showCreditGate && (
            <>
              {phase === 'summary' && renderSummaryPhase()}
              {phase === 'prediction' && renderPredictionPhase()}
              {phase === 'recommendation' && renderRecommendationPhase()}
              {phase === 'research' && renderResearchPhase()}
            </>
          )}
        </div>

        {/* Footer breadcrumb */}
        {phaseHistory.length > 0 && !showCreditGate && (
          <div className="px-6 py-2 border-t border-white/5 text-xs text-white/30">
            {['summary', ...phaseHistory.filter(p => p !== 'summary')].map((p, i) => (
              <span key={i}>
                {i > 0 && ' > '}
                <button
                  onClick={() => {
                    setPhase(p as AnalysisPhase);
                    setPhaseHistory([]);
                    setShowCreditGate(false);
                    setLoadingStatus('idle');
                  }}
                  className="hover:text-white/60 transition-colors"
                >
                  {phaseTitle[p as AnalysisPhase]}
                </button>
              </span>
            ))}
            {' > '}{phaseTitle[phase]}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
