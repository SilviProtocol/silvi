'use client';

import { useState, useEffect, useRef } from 'react';
import { useMapEvents, useMap, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import HabitatPredictionModal from './HabitatPredictionModal';

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

      // Set clicked location and show modal
      setClickedLocation({ lat, lon: lng });
      setShowPredictionModal(true);
      console.log('Modal should now be showing...');
    },
  });

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
              <strong>Prediction Location</strong>
              <br />
              {clickedLocation.lat.toFixed(4)}, {clickedLocation.lon.toFixed(4)}
            </div>
          </Popup>
        </Marker>
      )}

      {/* Prediction Modal */}
      {showPredictionModal && clickedLocation && (
        <HabitatPredictionModal
          lat={clickedLocation.lat}
          lon={clickedLocation.lon}
          map={map}
          onClose={() => {
            setShowPredictionModal(false);
            // Optionally clear marker: setClickedLocation(null);
          }}
        />
      )}
    </>
  );
}
