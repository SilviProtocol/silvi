'use client';

import { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { PlotAnalysisResponse, AOIDefinition } from '@/lib/types';
import { X, ChevronDown, ChevronUp } from 'lucide-react';

// Import components - Map dynamically to avoid SSR issues with Leaflet
const Map = dynamic(() => import('./components/Map'), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center bg-black/30">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500 mx-auto mb-2"></div>
        <p className="text-white/80">Loading map...</p>
      </div>
    </div>
  )
});

// AnalysisModal also needs dynamic import (uses Leaflet L.DomEvent)
const AnalysisModal = dynamic(() => import('./components/AnalysisModal'), { ssr: false });

import FileUpload from './components/FileUpload';

export default function AnalysisPage() {
  const [analysisResults, setAnalysisResults] = useState<PlotAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isHeatmapLoading, setIsHeatmapLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // KML panel
  const [showKMLPanel, setShowKMLPanel] = useState(false);
  const [isKMLMinimized, setIsKMLMinimized] = useState(false);

  // Unified Analysis Modal state
  const [activeAOI, setActiveAOI] = useState<AOIDefinition | null>(null);
  const [activeSummary, setActiveSummary] = useState<PlotAnalysisResponse | null>(null);
  const [showModal, setShowModal] = useState(false);

  const handleAnalysisComplete = (results: PlotAnalysisResponse) => {
    setAnalysisResults(results);
    setError(null);
  };

  const handleAnalysisError = (errorMessage: string) => {
    setError(errorMessage);
    setAnalysisResults(null);
  };

  const handleLoadingChange = (loading: boolean) => {
    setIsLoading(loading);
  };

  const handleHeatmapLoadingChange = (loading: boolean) => {
    setIsHeatmapLoading(loading);
  };

  const clearResults = () => {
    setAnalysisResults(null);
    setError(null);
    setIsHeatmapLoading(false);
    setShowKMLPanel(false);
    setShowModal(false);
    setActiveAOI(null);
    setActiveSummary(null);
  };

  // Handle showing KML panel
  const handleShowKMLPanel = () => {
    setShowKMLPanel(true);
    setIsKMLMinimized(false);
  };

  // Handle AOI defined — opens the unified modal
  const handleAOIDefined = useCallback((aoi: AOIDefinition, summary: PlotAnalysisResponse) => {
    setActiveAOI(aoi);
    setActiveSummary(summary);
    setShowModal(true);
  }, []);

  const handleCloseModal = useCallback(() => {
    setShowModal(false);
  }, []);

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-black/30 backdrop-blur-md border-b border-white/20 flex-shrink-0">
        <div className="max-w-full px-4 sm:px-6 lg:px-8">
          <div className="py-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="text-2xl">🗺️</div>
                <div className="flex items-baseline gap-3">
                  <h1 className="text-xl font-bold text-white">
                    GIS Analysis
                  </h1>
                  <span className="text-white/60 text-sm">
                    Draw polygons, click points, or upload KML files to analyze species
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Full-screen map with overlay panels */}
      <div className="flex-1 relative">
        <Map
          onAnalysisComplete={handleAnalysisComplete}
          onAnalysisError={handleAnalysisError}
          onLoadingChange={handleLoadingChange}
          onHeatmapLoadingChange={handleHeatmapLoadingChange}
          onClear={clearResults}
          isAnalysisLoading={isLoading}
          onShowKMLPanel={handleShowKMLPanel}
          onAOIDefined={handleAOIDefined}
        />

        {/* KML Upload Panel */}
        <div className="absolute top-4 left-16 z-[1000] space-y-4 max-w-md">
          {showKMLPanel && (
            <div className="rounded-xl bg-black/80 backdrop-blur-md border border-white/20 shadow-2xl">
              <div className="p-4 border-b border-white/20 flex items-center justify-between">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-emerald-300 mb-1">
                    KML Upload
                  </h3>
                  {!isKMLMinimized && (
                    <p className="text-sm text-white/70">
                      Upload a KML file to analyze species boundaries
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1 ml-2">
                  <button
                    onClick={() => setIsKMLMinimized(!isKMLMinimized)}
                    className="p-1 hover:bg-white/10 rounded transition-colors"
                    aria-label={isKMLMinimized ? "Expand" : "Minimize"}
                  >
                    {isKMLMinimized ? (
                      <ChevronDown className="w-5 h-5 text-white/80" />
                    ) : (
                      <ChevronUp className="w-5 h-5 text-white/80" />
                    )}
                  </button>
                  <button
                    onClick={() => setShowKMLPanel(false)}
                    className="p-1 hover:bg-white/10 rounded transition-colors"
                    aria-label="Close"
                  >
                    <X className="w-5 h-5 text-white/80" />
                  </button>
                </div>
              </div>
              {!isKMLMinimized && (
                <div className="p-4">
                  <FileUpload
                    onAnalysisComplete={handleAnalysisComplete}
                    onAnalysisError={handleAnalysisError}
                    onLoadingChange={handleLoadingChange}
                    onAOIDefined={handleAOIDefined}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Unified Analysis Modal */}
        {showModal && activeAOI && activeSummary && (
          <AnalysisModal
            aoi={activeAOI}
            initialSummary={activeSummary}
            onClose={handleCloseModal}
          />
        )}
      </div>
    </div>
  );
}
