'use client';

import { useState, useEffect, useRef } from 'react';
import { useMapEvents, useMap, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import HabitatPredictionModal from './HabitatPredictionModal';
import SpeciesRecommenderModal from './SpeciesRecommenderModal';
import SiteInspectorModal from './SiteInspectorModal';

// Custom icon for clicked location - modern circular design
const clickedLocationIcon = L.divIcon({
  className: 'custom-map-marker',
  html: `
    <div style="
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      border: 3px solid white;
      border-radius: 50%;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
    ">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
      </svg>
    </div>
  `,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  popupAnchor: [0, -16]
});

interface MapClickHandlerProps {
  enabled?: boolean;
}

export default function MapClickHandler({ enabled = true }: MapClickHandlerProps) {
  const [clickedLocation, setClickedLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [showPredictionModal, setShowPredictionModal] = useState(false);
  const [showRecommenderModal, setShowRecommenderModal] = useState(false);
  const [showSiteInspectorModal, setShowSiteInspectorModal] = useState(false);
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [isDrawing, setIsDrawing] = useState(false);

  // Get map instance to pass to modal
  const map = useMap();

  // Listen for leaflet-draw events to detect when drawing mode is active
  useEffect(() => {
    if (!map) return;

    const onDrawStart = () => {
      console.log('Drawing started - disabling click handler');
      setIsDrawing(true);
    };

    const onDrawStop = () => {
      console.log('Drawing stopped - enabling click handler');
      // Small delay to prevent the final click from triggering prediction
      setTimeout(() => setIsDrawing(false), 100);
    };

    const onDrawCreated = () => {
      console.log('Draw created - enabling click handler');
      setTimeout(() => setIsDrawing(false), 100);
    };

    // Listen for draw events
    map.on('draw:drawstart', onDrawStart);
    map.on('draw:drawstop', onDrawStop);
    map.on('draw:created', onDrawCreated);
    map.on('draw:editstart', onDrawStart);
    map.on('draw:editstop', onDrawStop);
    map.on('draw:deletestart', onDrawStart);
    map.on('draw:deletestop', onDrawStop);

    return () => {
      map.off('draw:drawstart', onDrawStart);
      map.off('draw:drawstop', onDrawStop);
      map.off('draw:created', onDrawCreated);
      map.off('draw:editstart', onDrawStart);
      map.off('draw:editstop', onDrawStop);
      map.off('draw:deletestart', onDrawStart);
      map.off('draw:deletestop', onDrawStop);
    };
  }, [map]);

  useMapEvents({
    click: (e) => {
      console.log('=== MAP CLICK EVENT FIRED ===');
      console.log('Enabled:', enabled, 'IsDrawing:', isDrawing);

      if (!enabled || isDrawing) {
        console.log('MapClickHandler is disabled or drawing mode active, ignoring click');
        return;
      }

      // Check if click originated from a leaflet-draw control or toolbar
      const target = e.originalEvent?.target as HTMLElement;
      if (target) {
        // Check if the click is on a draw control element
        const isDrawControl = target.closest('.leaflet-draw') ||
                              target.closest('.leaflet-draw-toolbar') ||
                              target.closest('.leaflet-draw-section');
        if (isDrawControl) {
          console.log('Click on draw control, ignoring');
          return;
        }
      }

      const { lat, lng } = e.latlng;
      console.log(`Map clicked at: (${lat}, ${lng})`);

      // Set clicked location and show mode selector
      setClickedLocation({ lat, lon: lng });
      setShowModeSelector(true);
    },
  });

  // Helper to create portal outside Leaflet's DOM
  const ModeSelector = ({ lat, lon, onPredict, onRecommend, onInspect, onClose }: {
    lat: number; lon: number;
    onPredict: () => void; onRecommend: () => void; onInspect: () => void; onClose: () => void;
  }) => {
    if (typeof window === 'undefined') return null;
    const { createPortal } = require('react-dom');
    return createPortal(
      <div className="fixed inset-0 z-[10000] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
        <div className="bg-gray-900/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
          <div className="text-center">
            <h2 className="text-lg font-semibold text-white">Location Analysis</h2>
            <p className="text-sm text-white/50 mt-1">
              {lat.toFixed(4)}, {lon.toFixed(4)}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3">
            <button
              onClick={onPredict}
              className="p-4 rounded-xl border border-blue-500/30 bg-blue-500/10 hover:bg-blue-500/20 transition-all text-left group"
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">🔍</span>
                <div>
                  <div className="text-white font-medium group-hover:text-blue-400 transition-colors">
                    Species Predictor
                  </div>
                  <div className="text-xs text-white/50 mt-0.5">
                    What species CAN grow here? Scientific habitat suitability analysis.
                  </div>
                </div>
              </div>
            </button>

            <button
              onClick={onRecommend}
              className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 transition-all text-left group"
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">🌱</span>
                <div>
                  <div className="text-white font-medium group-hover:text-emerald-400 transition-colors">
                    Species Recommender
                  </div>
                  <div className="text-xs text-white/50 mt-0.5">
                    What SHOULD I plant here? Strategy-based SAFE-B recommendations.
                  </div>
                </div>
              </div>
            </button>

            <button
              onClick={onInspect}
              className="p-4 rounded-xl border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 transition-all text-left group"
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">🛰️</span>
                <div>
                  <div className="text-white font-medium group-hover:text-cyan-400 transition-colors">
                    Site Inspector
                  </div>
                  <div className="text-xs text-white/50 mt-0.5">
                    What IS this place? Environmental context from 35+ satellite layers.
                  </div>
                </div>
              </div>
            </button>
          </div>

          <button
            onClick={onClose}
            className="w-full py-2 text-sm text-white/40 hover:text-white/60 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>,
      document.body
    );
  };

  return (
    <>
      {/* Show marker at clicked location */}
      {clickedLocation && (
        <Marker
          position={[clickedLocation.lat, clickedLocation.lon]}
          icon={clickedLocationIcon}
        >
          <Popup>
            <div className="text-sm">
              <strong>Analysis Location</strong>
              <br />
              {clickedLocation.lat.toFixed(4)}, {clickedLocation.lon.toFixed(4)}
            </div>
          </Popup>
        </Marker>
      )}

      {/* Mode Selector: Predict vs Recommend vs Inspect */}
      {showModeSelector && clickedLocation && !showPredictionModal && !showRecommenderModal && !showSiteInspectorModal && (
        <ModeSelector
          lat={clickedLocation.lat}
          lon={clickedLocation.lon}
          onPredict={() => {
            setShowModeSelector(false);
            setShowPredictionModal(true);
          }}
          onRecommend={() => {
            setShowModeSelector(false);
            setShowRecommenderModal(true);
          }}
          onInspect={() => {
            setShowModeSelector(false);
            setShowSiteInspectorModal(true);
          }}
          onClose={() => setShowModeSelector(false)}
        />
      )}

      {/* Prediction Modal */}
      {showPredictionModal && clickedLocation && (
        <HabitatPredictionModal
          lat={clickedLocation.lat}
          lon={clickedLocation.lon}
          map={map}
          onClose={() => {
            setShowPredictionModal(false);
          }}
        />
      )}

      {/* Recommender Modal */}
      {showRecommenderModal && clickedLocation && (
        <SpeciesRecommenderModal
          lat={clickedLocation.lat}
          lon={clickedLocation.lon}
          onClose={() => {
            setShowRecommenderModal(false);
          }}
        />
      )}

      {/* Site Inspector Modal */}
      {showSiteInspectorModal && clickedLocation && (
        <SiteInspectorModal
          lat={clickedLocation.lat}
          lon={clickedLocation.lon}
          map={map}
          onClose={() => {
            setShowSiteInspectorModal(false);
          }}
        />
      )}
    </>
  );
}
