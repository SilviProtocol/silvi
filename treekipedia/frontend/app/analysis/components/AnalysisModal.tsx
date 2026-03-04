'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  X, Loader2, ChevronLeft, MapPin, Trees, Sparkles, Leaf,
  AlertCircle, TreePine, Sprout, Droplets, Wind, Bug
} from 'lucide-react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import L from 'leaflet';
import {
  AOIDefinition, AnalysisPhase, RecommendationStrategy,
  PlotAnalysisResponse, BulkResearchStatusResponse
} from '@/lib/types';
import {
  predictPolygonSpecies, checkBulkResearchStatus, triggerResearch
} from '@/lib/api';
import { useCredits } from '@/hooks/useCredits';
import { CreditGate } from '@/components/CreditGate';
import CrossAnalysisSummary from './CrossAnalysisSummary';

// ============================================
// Inline Types
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

const STRATEGIES: { key: RecommendationStrategy; label: string; desc: string; icon: React.ReactNode; color: string }[] = [
  { key: 'general', label: 'General Restoration', desc: 'Balanced species mix for ecosystem health', icon: <Trees className="h-5 w-5" />, color: 'emerald' },
  { key: 'rewilding', label: 'Rewilding', desc: 'Native species for ecological recovery', icon: <TreePine className="h-5 w-5" />, color: 'teal' },
  { key: 'agroforestry', label: 'Agroforestry', desc: 'Species with productive value', icon: <Sprout className="h-5 w-5" />, color: 'lime' },
  { key: 'riparian', label: 'Riparian', desc: 'Waterway buffer zone species', icon: <Droplets className="h-5 w-5" />, color: 'cyan' },
  { key: 'carbon', label: 'Carbon Sequestration', desc: 'Maximum carbon capture potential', icon: <Wind className="h-5 w-5" />, color: 'sky' },
  { key: 'biodiversity', label: 'Biodiversity', desc: 'Maximize species diversity', icon: <Bug className="h-5 w-5" />, color: 'violet' },
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
// Stagger animation wrapper
// ============================================

function Stagger({ children, delay = 0, className = '' }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <div
      className={`animate-fade-up ${className}`}
      style={{ animationDelay: `${delay}ms`, animationFillMode: 'both' }}
    >
      {children}
    </div>
  );
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

  // Portal mount + entrance animation
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
    // Trigger entrance after mount
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setVisible(true));
    });
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
  // Research status dot
  // ============================================

  const ResearchDot = ({ taxonId }: { taxonId: string }) => {
    const status = researchStatuses[taxonId];
    if (!status) return <div className="w-2 h-2 rounded-full bg-white/20 ring-1 ring-white/10" title="Unknown" />;
    const config = {
      researched: { bg: 'bg-emerald-400', ring: 'ring-emerald-400/30', glow: 'shadow-[0_0_6px_rgba(52,211,153,0.4)]' },
      partial: { bg: 'bg-amber-400', ring: 'ring-amber-400/30', glow: 'shadow-[0_0_6px_rgba(251,191,36,0.4)]' },
      unresearched: { bg: 'bg-white/20', ring: 'ring-white/10', glow: '' },
    };
    const c = config[status];
    const labels = { researched: 'Researched', partial: 'Partially researched', unresearched: 'Not researched' };
    return <div className={`w-2 h-2 rounded-full ${c.bg} ring-1 ${c.ring} ${c.glow}`} title={labels[status]} />;
  };

  // ============================================
  // Native status badge
  // ============================================

  const NativeBadge = ({ prediction }: { prediction: PolygonPrediction }) => {
    if (prediction.is_native) return (
      <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
        Native
      </span>
    );
    if (prediction.is_invasive) return (
      <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-red-500/15 text-red-300 border border-red-500/25">
        Invasive
      </span>
    );
    if (prediction.is_introduced) return (
      <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/25">
        Introduced
      </span>
    );
    return null;
  };

  // ============================================
  // Suitability color
  // ============================================

  const suitabilityColor = (pct: number) => {
    if (pct >= 80) return { bar: 'from-emerald-500 to-emerald-300', text: 'text-emerald-300' };
    if (pct >= 60) return { bar: 'from-teal-500 to-teal-300', text: 'text-teal-300' };
    if (pct >= 40) return { bar: 'from-amber-500 to-amber-300', text: 'text-amber-300' };
    return { bar: 'from-orange-500 to-orange-300', text: 'text-orange-300' };
  };

  // ============================================
  // Species list renderer
  // ============================================

  const renderSpeciesList = (predictions: PolygonPrediction[]) => {
    const displayed = predictions.slice(0, displayLimit);
    const unresearchedCount = predictions.filter(p => researchStatuses[p.taxon_id] === 'unresearched').length;
    const researchCost = unresearchedCount * 25;

    return (
      <div className="space-y-2">
        {/* Legend bar */}
        <Stagger delay={0}>
          <div className="flex items-center justify-between text-xs text-white/40 px-1 mb-1">
            <span className="font-medium tracking-wide uppercase">{predictions.length} species</span>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_4px_rgba(52,211,153,0.5)]" />
                Researched
              </span>
              <span className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-400 shadow-[0_0_4px_rgba(251,191,36,0.5)]" />
                Partial
              </span>
              <span className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
                None
              </span>
            </div>
          </div>
        </Stagger>

        {/* Species cards */}
        {displayed.map((pred, idx) => {
          const pct = Math.round(pred.avg_suitability * 100);
          const colors = suitabilityColor(pct);
          return (
            <Stagger key={pred.taxon_id} delay={Math.min(idx * 30, 300)}>
              <Link
                href={`/species/${pred.taxon_id}`}
                target="_blank"
                className="group block rounded-lg border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05] hover:border-emerald-500/20 transition-all duration-200 overflow-hidden"
              >
                <div className="flex items-center gap-3 p-3">
                  {/* Research dot */}
                  <div className="shrink-0">
                    <ResearchDot taxonId={pred.taxon_id} />
                  </div>

                  {/* Species info */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-white/90 font-medium text-sm truncate">
                        {pred.common_name || pred.scientific_name}
                      </span>
                      <NativeBadge prediction={pred} />
                    </div>
                    <div className="text-white/30 text-xs italic truncate mt-0.5">
                      {pred.scientific_name}
                      {pred.family && <span className="not-italic text-white/20 ml-2">{pred.family}</span>}
                    </div>
                  </div>

                  {/* Suitability score */}
                  <div className="shrink-0 text-right">
                    <div className={`text-lg font-bold tabular-nums tracking-tight ${colors.text}`}>
                      {pct}<span className="text-[10px] font-normal opacity-60">%</span>
                    </div>
                  </div>
                </div>

                {/* Suitability bar — flush bottom edge */}
                <div className="h-0.5 bg-black/20">
                  <div
                    className={`h-full bg-gradient-to-r ${colors.bar} transition-all duration-500 group-hover:opacity-100 opacity-70`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </Link>
            </Stagger>
          );
        })}

        {/* Show more */}
        {predictions.length > displayLimit && (
          <button
            onClick={() => setDisplayLimit(prev => prev + 50)}
            className="w-full py-2.5 text-xs font-medium tracking-wide uppercase text-white/30 hover:text-emerald-300 border border-dashed border-white/[0.06] hover:border-emerald-500/20 rounded-lg transition-all duration-200"
          >
            Show more ({predictions.length - displayLimit} remaining)
          </button>
        )}

        {/* Research CTA */}
        {unresearchedCount > 0 && isAuth && (
          <Stagger delay={400}>
            <div className="mt-3 relative overflow-hidden rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-950/40 via-emerald-900/20 to-transparent p-4">
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(52,211,153,0.08),transparent_60%)]" />
              <div className="relative">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-white/80 text-sm">
                    <span className="font-semibold text-white">{unresearchedCount}</span> species awaiting research
                  </span>
                  <span className="text-amber-300/80 text-sm font-medium tabular-nums">
                    {researchCost} credits
                  </span>
                </div>
                <button
                  onClick={() => requireAuthAndCredits(researchCost, 'Research Remaining Species', runResearch)}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-semibold tracking-wide transition-all duration-200 hover:shadow-[0_0_20px_rgba(52,211,153,0.2)]"
                >
                  Research & Generate Guide
                </button>
              </div>
            </div>
          </Stagger>
        )}
      </div>
    );
  };

  // ============================================
  // Phase: Summary
  // ============================================

  const renderSummaryPhase = () => (
    <div className="space-y-5">
      {/* AOI badge */}
      <Stagger delay={0}>
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-white/50 text-xs">
          <MapPin className="h-3 w-3" />
          {aoi.type === 'polygon' ? 'Drawn polygon' :
           aoi.type === 'point' ? 'Point buffer (~1 km)' :
           aoi.label || 'Uploaded KML'}
        </div>
      </Stagger>

      {/* Summary stats — asymmetric layout */}
      <Stagger delay={60}>
        <div className="grid grid-cols-5 gap-3">
          <div className="col-span-3 relative overflow-hidden rounded-xl border border-emerald-500/15 bg-gradient-to-br from-emerald-950/30 to-transparent p-5">
            <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl -translate-y-1/2 translate-x-1/2" />
            <div className="relative">
              <div className="text-4xl font-bold tracking-tight text-emerald-300">
                {initialSummary.totalSpecies}
              </div>
              <div className="text-xs text-white/40 mt-1 font-medium tracking-wide uppercase">Species Found</div>
            </div>
          </div>
          <div className="col-span-2 relative overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
            <div className="text-3xl font-bold tracking-tight text-white/80 tabular-nums">
              {initialSummary.totalOccurrences.toLocaleString()}
            </div>
            <div className="text-xs text-white/30 mt-1 font-medium tracking-wide uppercase">Occurrences</div>
          </div>
        </div>
      </Stagger>

      {/* Cross analysis */}
      {initialSummary.crossAnalysis && (
        <Stagger delay={120}>
          <CrossAnalysisSummary
            crossAnalysis={initialSummary.crossAnalysis}
            totalSpecies={initialSummary.totalSpecies}
          />
        </Stagger>
      )}

      {/* CTA buttons — the hero section */}
      <Stagger delay={180}>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => requireAuthAndCredits(25, 'Species Prediction (AlphaEarth)', runPrediction)}
            className="group relative overflow-hidden rounded-xl border border-blue-500/15 p-5 text-left transition-all duration-300 hover:border-blue-400/30 hover:shadow-[0_0_30px_rgba(59,130,246,0.08)]"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-blue-950/30 via-blue-900/10 to-transparent opacity-60 group-hover:opacity-100 transition-opacity duration-300" />
            <div className="relative">
              <Sparkles className="h-6 w-6 text-blue-400/80 group-hover:text-blue-300 transition-colors mb-3" />
              <div className="text-white font-semibold text-sm mb-1">Species Prediction</div>
              <div className="text-white/30 text-xs leading-relaxed">AlphaEarth satellite habitat analysis</div>
              <div className="mt-3 text-amber-300/60 text-xs font-medium">25 credits</div>
            </div>
          </button>
          <button
            onClick={() => navigateTo('recommendation')}
            className="group relative overflow-hidden rounded-xl border border-emerald-500/15 p-5 text-left transition-all duration-300 hover:border-emerald-400/30 hover:shadow-[0_0_30px_rgba(52,211,153,0.08)]"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-950/30 via-emerald-900/10 to-transparent opacity-60 group-hover:opacity-100 transition-opacity duration-300" />
            <div className="relative">
              <Leaf className="h-6 w-6 text-emerald-400/80 group-hover:text-emerald-300 transition-colors mb-3" />
              <div className="text-white font-semibold text-sm mb-1">Species Recommendation</div>
              <div className="text-white/30 text-xs leading-relaxed">LEAF ecological scoring by strategy</div>
              <div className="mt-3 text-amber-300/60 text-xs font-medium">25 credits</div>
            </div>
          </button>
        </div>
      </Stagger>

      {/* Occurrence species list */}
      {initialSummary.species.length > 0 && (
        <Stagger delay={240}>
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="h-px flex-1 bg-gradient-to-r from-white/[0.06] to-transparent" />
              <span className="text-[10px] font-semibold tracking-widest uppercase text-white/25">
                Occurrence Data ({initialSummary.species.length})
              </span>
              <div className="h-px flex-1 bg-gradient-to-l from-white/[0.06] to-transparent" />
            </div>
            <div className="space-y-1 max-h-[280px] overflow-y-auto pr-1 scrollbar-thin">
              {initialSummary.species.slice(0, 20).map((sp, idx) => (
                <Link
                  key={sp.taxon_id}
                  href={`/species/${sp.taxon_id}`}
                  target="_blank"
                  className="group flex items-center justify-between gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.03] transition-colors duration-150"
                >
                  <div className="min-w-0">
                    <div className="text-white/70 text-sm truncate group-hover:text-white/90 transition-colors">
                      {sp.common_name || sp.scientific_name}
                    </div>
                    <div className="text-white/25 text-xs italic truncate">{sp.scientific_name}</div>
                  </div>
                  <div className="shrink-0 tabular-nums text-right">
                    <span className="text-emerald-400/70 text-sm font-semibold">{sp.occurrences}</span>
                  </div>
                </Link>
              ))}
              {initialSummary.species.length > 20 && (
                <div className="text-center text-white/20 text-xs py-2">
                  + {initialSummary.species.length - 20} more
                </div>
              )}
            </div>
          </div>
        </Stagger>
      )}
    </div>
  );

  // ============================================
  // Phase: Prediction
  // ============================================

  const renderPredictionPhase = () => {
    if (loadingStatus === 'loading') return renderLoadingState();
    if (loadingStatus === 'error') return renderErrorState();
    if (!predictionData) return null;

    return (
      <div className="space-y-4">
        {/* Location context */}
        {locationContext && locationContext.ecoregions.length > 0 && (
          <Stagger delay={0}>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="text-[10px] font-semibold tracking-widest uppercase text-white/30 mb-2">Ecoregion Context</div>
              {locationContext.ecoregions.slice(0, 3).map(eco => (
                <div key={eco.eco_id} className="text-white/80 text-sm leading-relaxed">
                  {eco.eco_name}
                  <span className="text-white/25 ml-1.5">{eco.biome_name}</span>
                </div>
              ))}
              {locationContext.countries.length > 0 && (
                <div className="text-white/25 text-xs mt-2 font-medium">
                  {locationContext.countries.join(' / ')}
                </div>
              )}
            </div>
          </Stagger>
        )}

        {/* Polygon metrics */}
        {predictionData.polygon_summary && (
          <Stagger delay={60}>
            <div className="flex items-center gap-4 text-xs text-white/30 font-medium">
              <span className="tabular-nums">{predictionData.polygon_summary.approx_area_km2.toFixed(1)} km²</span>
              <span className="w-px h-3 bg-white/10" />
              <span className="tabular-nums">{predictionData.polygon_summary.sample_points_succeeded} sample pts</span>
              <span className="w-px h-3 bg-white/10" />
              <span className="tabular-nums">{predictionData.results.species_count} species</span>
            </div>
          </Stagger>
        )}

        {renderSpeciesList(predictionData.results.predictions)}
      </div>
    );
  };

  // ============================================
  // Phase: Recommendation
  // ============================================

  const renderRecommendationPhase = () => {
    // Strategy picker
    if (!selectedStrategy && loadingStatus === 'idle') {
      return (
        <div className="space-y-5">
          <Stagger delay={0}>
            <p className="text-white/40 text-sm leading-relaxed">
              Choose a restoration strategy to get species recommendations tailored to your goals.
            </p>
          </Stagger>
          <div className="grid grid-cols-2 gap-2.5">
            {STRATEGIES.map((s, idx) => (
              <Stagger key={s.key} delay={60 + idx * 40} className="h-full">
                <button
                  onClick={() => requireAuthAndCredits(25, `${s.label} Recommendation`, () => runRecommendation(s.key))}
                  className="group relative overflow-hidden rounded-xl border border-white/[0.06] p-4 text-left transition-all duration-200 hover:border-emerald-500/20 hover:bg-white/[0.02] w-full h-full flex flex-col"
                >
                  <div className="text-emerald-400/60 group-hover:text-emerald-300 transition-colors mb-2">
                    {s.icon}
                  </div>
                  <div className="text-white/80 text-sm font-medium mb-0.5">{s.label}</div>
                  <div className="text-white/25 text-xs leading-relaxed flex-1">{s.desc}</div>
                </button>
              </Stagger>
            ))}
          </div>
          <Stagger delay={320}>
            <div className="text-center text-amber-300/40 text-xs font-medium">25 credits per recommendation</div>
          </Stagger>
        </div>
      );
    }

    if (loadingStatus === 'loading') return renderLoadingState();
    if (loadingStatus === 'error') return renderErrorState();
    if (!recommendationData) return null;

    return (
      <div className="space-y-4">
        {selectedStrategy && (
          <Stagger delay={0}>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/15 text-emerald-300/80 text-xs font-medium">
              <Leaf className="h-3 w-3" />
              {STRATEGIES.find(s => s.key === selectedStrategy)?.label}
            </div>
          </Stagger>
        )}

        {locationContext && locationContext.ecoregions.length > 0 && (
          <Stagger delay={60}>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="text-[10px] font-semibold tracking-widest uppercase text-white/30 mb-2">Ecoregion Context</div>
              {locationContext.ecoregions.slice(0, 3).map(eco => (
                <div key={eco.eco_id} className="text-white/80 text-sm leading-relaxed">
                  {eco.eco_name}
                  <span className="text-white/25 ml-1.5">{eco.biome_name}</span>
                </div>
              ))}
            </div>
          </Stagger>
        )}

        {renderSpeciesList(recommendationData.results.predictions)}
      </div>
    );
  };

  // ============================================
  // Phase: Research
  // ============================================

  const renderResearchPhase = () => {
    if (loadingStatus === 'loading') {
      return (
        <div className="py-12 space-y-6">
          <Stagger delay={0}>
            <div className="text-center">
              <div className="relative mx-auto w-14 h-14 mb-4">
                <div className="absolute inset-0 rounded-full bg-emerald-500/10 animate-ping" />
                <div className="relative w-full h-full flex items-center justify-center">
                  <Loader2 className="h-7 w-7 animate-spin text-emerald-400" />
                </div>
              </div>
              <div className="text-white/90 font-medium text-sm">{statusMessage}</div>
              <div className="text-white/30 text-xs mt-1 tabular-nums">
                {researchProgress} / {researchTotal}
              </div>
            </div>
          </Stagger>
          <div className="relative h-1.5 rounded-full bg-black/30 overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-emerald-400/50 to-emerald-300/50 blur-sm transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          {researchingTaxonId && (
            <div className="text-center text-white/20 text-xs font-mono">
              {researchingTaxonId}
            </div>
          )}
        </div>
      );
    }

    if (loadingStatus === 'error') return renderErrorState();

    if (loadingStatus === 'complete') {
      return (
        <div className="py-12 text-center space-y-5">
          <Stagger delay={0}>
            <div className="relative mx-auto w-16 h-16">
              <div className="absolute inset-0 rounded-full bg-emerald-500/10 animate-pulse" />
              <div className="relative w-full h-full flex items-center justify-center text-emerald-400 text-3xl">
                &#10003;
              </div>
            </div>
          </Stagger>
          <Stagger delay={100}>
            <h3 className="text-white font-semibold text-lg tracking-tight">Research Complete</h3>
            <p className="text-white/40 text-sm leading-relaxed max-w-xs mx-auto">
              {researchTotal} species researched. Data is now available on each species page.
            </p>
          </Stagger>
          <Stagger delay={200}>
            <button
              onClick={() => {
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
              className="px-6 py-2.5 bg-white/[0.06] hover:bg-white/[0.1] text-white/80 rounded-lg text-sm font-medium transition-all duration-200 border border-white/[0.06]"
            >
              Back to Results
            </button>
          </Stagger>
        </div>
      );
    }

    return null;
  };

  // ============================================
  // Shared: Loading
  // ============================================

  const renderLoadingState = () => (
    <div className="py-12 space-y-6">
      <div className="text-center">
        <div className="relative mx-auto w-14 h-14 mb-4">
          <div className="absolute inset-0 rounded-full bg-emerald-500/10 animate-ping" />
          <div className="relative w-full h-full flex items-center justify-center">
            <Loader2 className="h-7 w-7 animate-spin text-emerald-400" />
          </div>
        </div>
        <div className="text-white/80 font-medium text-sm">{statusMessage}</div>
      </div>
      <div className="relative h-1.5 rounded-full bg-black/30 overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all duration-700"
          style={{ width: `${progress}%` }}
        />
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-emerald-400/50 to-emerald-300/50 blur-sm transition-all duration-700"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );

  // ============================================
  // Shared: Error
  // ============================================

  const renderErrorState = () => (
    <div className="py-12 text-center space-y-4">
      <div className="mx-auto w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center">
        <AlertCircle className="h-6 w-6 text-red-400/80" />
      </div>
      <div className="text-white/80 font-medium">Something went wrong</div>
      <div className="text-white/30 text-sm max-w-xs mx-auto">{errorMessage}</div>
      <button
        onClick={goBack}
        className="px-5 py-2 bg-white/[0.06] hover:bg-white/[0.1] text-white/70 rounded-lg text-sm transition-all duration-200 border border-white/[0.06]"
      >
        Go Back
      </button>
    </div>
  );

  // ============================================
  // Phase titles
  // ============================================

  const phaseConfig: Record<AnalysisPhase, { title: string; icon: React.ReactNode }> = {
    summary: { title: 'Site Analysis', icon: <MapPin className="h-4 w-4" /> },
    prediction: { title: 'Species Prediction', icon: <Sparkles className="h-4 w-4" /> },
    recommendation: { title: 'Species Recommendation', icon: <Leaf className="h-4 w-4" /> },
    research: { title: 'Species Research', icon: <Trees className="h-4 w-4" /> },
  };

  // ============================================
  // Render
  // ============================================

  if (!mounted) return null;

  const modalContent = (
    <div
      ref={overlayRef}
      className={`fixed inset-0 z-[9999] flex items-center justify-center transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-0'}`}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-md"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        ref={modalRef}
        className={`relative w-full max-w-2xl max-h-[85vh] mx-4 flex flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-[#0a0f0d]/95 backdrop-blur-xl shadow-[0_0_80px_rgba(0,0,0,0.6)] transition-all duration-300 ${visible ? 'translate-y-0 scale-100' : 'translate-y-4 scale-[0.98]'}`}
      >
        {/* Decorative top gradient line */}
        <div className="h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent" />

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            {phaseHistory.length > 0 && (
              <button
                onClick={goBack}
                className="text-white/30 hover:text-white/70 transition-colors duration-200 -ml-1"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}
            <div className="text-emerald-400/60">
              {phaseConfig[phase].icon}
            </div>
            <h2 className="text-white/90 font-semibold tracking-tight">
              {phaseConfig[phase].title}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-white/20 hover:text-white/60 transition-colors duration-200 p-1 rounded-lg hover:bg-white/[0.04]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Subtle header divider */}
        <div className="h-px bg-gradient-to-r from-transparent via-white/[0.04] to-transparent" />

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 scrollbar-thin">
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
          <>
            <div className="h-px bg-gradient-to-r from-transparent via-white/[0.04] to-transparent" />
            <div className="px-6 py-2.5 text-[10px] font-medium tracking-wider uppercase text-white/20">
              {['summary', ...phaseHistory.filter(p => p !== 'summary')].map((p, i) => (
                <span key={i}>
                  {i > 0 && <span className="mx-1.5 text-white/10">/</span>}
                  <button
                    onClick={() => {
                      setPhase(p as AnalysisPhase);
                      setPhaseHistory([]);
                      setShowCreditGate(false);
                      setLoadingStatus('idle');
                    }}
                    className="hover:text-emerald-400/60 transition-colors duration-200"
                  >
                    {phaseConfig[p as AnalysisPhase].title}
                  </button>
                </span>
              ))}
              <span className="mx-1.5 text-white/10">/</span>
              <span className="text-white/30">{phaseConfig[phase].title}</span>
            </div>
          </>
        )}
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
