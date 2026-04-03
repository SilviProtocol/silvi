'use client';

import { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import {
  X, Loader2, MapPin, Thermometer, Droplets, Mountain,
  TreePine, Flame, Sun, Globe, ChevronDown, ChevronRight,
  AlertTriangle, Layers, Leaf
} from 'lucide-react';

// Types matching the Python /sample-env response structure
interface SiteField {
  key: string;
  label: string;
  value: string | number;
  unit: string;
  code?: number;
}

interface SiteSection {
  label: string;
  fields: SiteField[];
}

interface SiteContextResponse {
  success: boolean;
  lat: number;
  lon: number;
  elapsed_seconds: number;
  sections: {
    climate_water?: SiteSection;
    terrain_soil?: SiteSection;
    land_state?: SiteSection;
    carbon_productivity?: SiteSection;
    ecological_context?: SiteSection;
  };
  error?: string;
}

interface SiteInspectorModalProps {
  lat: number;
  lon: number;
  onClose: () => void;
  map?: L.Map | null;
}

// Section icon mapping
const SECTION_ICONS: Record<string, React.ReactNode> = {
  climate_water: <Droplets className="h-4 w-4" />,
  terrain_soil: <Mountain className="h-4 w-4" />,
  land_state: <Layers className="h-4 w-4" />,
  carbon_productivity: <TreePine className="h-4 w-4" />,
  ecological_context: <Globe className="h-4 w-4" />,
};

// Section accent colors
const SECTION_COLORS: Record<string, string> = {
  climate_water: 'text-blue-400',
  terrain_soil: 'text-amber-400',
  land_state: 'text-green-400',
  carbon_productivity: 'text-emerald-400',
  ecological_context: 'text-purple-400',
};

const SECTION_BORDER: Record<string, string> = {
  climate_water: 'border-blue-500/20',
  terrain_soil: 'border-amber-500/20',
  land_state: 'border-green-500/20',
  carbon_productivity: 'border-emerald-500/20',
  ecological_context: 'border-purple-500/20',
};

// Section order for consistent display
const SECTION_ORDER = [
  'climate_water',
  'terrain_soil',
  'land_state',
  'carbon_productivity',
  'ecological_context',
];

export default function SiteInspectorModal({ lat, lon, onClose, map }: SiteInspectorModalProps) {
  const [status, setStatus] = useState<'loading' | 'complete' | 'error'>('loading');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('Initializing...');
  const [data, setData] = useState<SiteContextResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(SECTION_ORDER) // All expanded by default
  );
  const [mounted, setMounted] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const modalRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const toggleSection = (key: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Portal mounting
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

  // Fetch site context data
  useEffect(() => {
    setStatus('loading');
    setProgress(0);
    setMessage('Initializing...');
    setData(null);
    setErrorMessage('');
    setElapsedTime(0);

    fetchSiteContext();

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [lat, lon]);

  const fetchSiteContext = async () => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';

    // Start elapsed timer
    const startTime = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedTime(Math.round((Date.now() - startTime) / 1000));
    }, 1000);

    try {
      setMessage('Connecting to Earth Engine...');
      setProgress(10);
      await new Promise(resolve => setTimeout(resolve, 200));

      setMessage('Sampling environmental features (~35 bands)...');
      setProgress(20);
      await new Promise(resolve => setTimeout(resolve, 200));

      setMessage('This typically takes 5-15 seconds...');
      setProgress(30);

      const response = await fetch(
        `${API_URL}/api/prediction/site-context?lat=${lat}&lon=${lon}`
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || errorData.detail || `Server error: ${response.status}`);
      }

      setMessage('Processing results...');
      setProgress(80);

      const result: SiteContextResponse = await response.json();

      if (!result.success) {
        throw new Error(result.error || 'Sampling failed');
      }

      setProgress(100);
      setMessage('Site context ready!');
      setData(result);
      setStatus('complete');

    } catch (error) {
      console.error('Site context error:', error);
      setStatus('error');
      setErrorMessage(error instanceof Error ? error.message : 'An unknown error occurred');
      setProgress(100);
    } finally {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  // Count total fields across all sections
  const totalFields = data
    ? Object.values(data.sections).reduce((sum, section) => sum + (section?.fields?.length || 0), 0)
    : 0;

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
        className="relative w-full max-w-2xl max-h-[90vh] bg-gradient-to-br from-gray-950 to-black border border-white/20 shadow-2xl rounded-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex-shrink-0 bg-gradient-to-r from-gray-900/90 to-gray-800/90 backdrop-blur-md px-6 py-4 border-b border-white/10 rounded-t-2xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Layers className="h-6 w-6 text-blue-400" />
              <div>
                <h2 className="text-xl font-semibold text-white">Site Inspector</h2>
                <p className="text-sm text-white/60">
                  <MapPin className="inline h-3 w-3 mr-1" />
                  {lat.toFixed(4)}, {lon.toFixed(4)}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white/60 hover:text-white transition-colors"
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
                <Loader2 className="h-12 w-12 text-blue-400 animate-spin" />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-blue-300">{message}</span>
                  <span className="text-blue-400 font-medium">{progress}%</span>
                </div>
                <div className="h-2 bg-gray-900 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-600 to-blue-400 transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>

              <p className="text-sm text-center text-white/50">
                Sampling satellite data from Google Earth Engine...
                {elapsedTime > 0 && (
                  <span className="ml-2 text-blue-400">{elapsedTime}s elapsed</span>
                )}
              </p>
            </div>
          )}

          {/* Error State */}
          {status === 'error' && (
            <div className="py-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 mb-4">
                <AlertTriangle className="h-8 w-8 text-red-400" />
              </div>
              <h3 className="text-lg font-medium text-white mb-2">Sampling Failed</h3>
              <p className="text-white/60 mb-4">{errorMessage}</p>
              <div className="flex gap-3 justify-center">
                <button
                  onClick={() => fetchSiteContext()}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
                >
                  Retry
                </button>
                <button
                  onClick={onClose}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {/* Success State */}
          {status === 'complete' && data && (
            <div className="space-y-3">
              {/* Summary bar */}
              <div className="flex items-center justify-between text-xs text-white/40 pb-2 border-b border-white/10">
                <span>{totalFields} environmental variables sampled</span>
                <span>Completed in {data.elapsed_seconds}s</span>
              </div>

              {/* Sections */}
              {SECTION_ORDER.map(sectionKey => {
                const section = data.sections[sectionKey as keyof typeof data.sections];
                if (!section || section.fields.length === 0) return null;

                const isExpanded = expandedSections.has(sectionKey);
                const icon = SECTION_ICONS[sectionKey];
                const color = SECTION_COLORS[sectionKey] || 'text-white';
                const border = SECTION_BORDER[sectionKey] || 'border-white/10';

                return (
                  <div key={sectionKey} className={`rounded-xl border ${border} bg-black/30 overflow-hidden`}>
                    {/* Section header */}
                    <button
                      onClick={() => toggleSection(sectionKey)}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <span className={color}>{icon}</span>
                        <span className="text-white font-medium text-sm">{section.label}</span>
                        <span className="text-white/30 text-xs">({section.fields.length})</span>
                      </div>
                      {isExpanded
                        ? <ChevronDown className="h-4 w-4 text-white/40" />
                        : <ChevronRight className="h-4 w-4 text-white/40" />
                      }
                    </button>

                    {/* Section fields */}
                    {isExpanded && (
                      <div className="px-4 pb-3 space-y-1">
                        {section.fields.map((field, idx) => (
                          <div
                            key={field.key}
                            className={`flex items-center justify-between py-1.5 ${
                              idx < section.fields.length - 1 ? 'border-b border-white/5' : ''
                            }`}
                          >
                            <span className="text-white/60 text-sm">{field.label}</span>
                            <span className="text-white font-medium text-sm tabular-nums">
                              {typeof field.value === 'number'
                                ? field.value.toLocaleString()
                                : field.value}
                              {field.unit && (
                                <span className="text-white/40 ml-1 text-xs">{field.unit}</span>
                              )}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Data caveats footer */}
              <div className="mt-4 p-3 rounded-lg bg-yellow-500/5 border border-yellow-500/20">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-yellow-500/70 flex-shrink-0 mt-0.5" />
                  <div className="text-xs text-yellow-200/60">
                    <p className="font-medium text-yellow-200/80 mb-1">Data Caveats</p>
                    <ul className="space-y-0.5 list-disc list-inside">
                      <li>GEDI canopy data unavailable above 51.6N latitude</li>
                      <li>JRC Tropical Moist Forest covers only tropical regions</li>
                      <li>Dynamic World available from 2015+; pre-2015 uses ESA WorldCover proxy</li>
                      <li>Soil data from OpenLandMap at 250m resolution (surface layer)</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  if (!mounted) return null;

  if (typeof window === 'undefined') return null;
  const { createPortal } = require('react-dom');
  return createPortal(modalContent, document.body);
}
