'use client';

import { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import 'leaflet-draw';
import 'leaflet.heat';
import { analyzePlot } from '@/lib/api';
import { PlotAnalysisResponse, GeoJSONPolygon } from '@/lib/types';
import { Layers } from 'lucide-react';

// Fix Leaflet icon issues with webpack
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

interface MapProps {
  onAnalysisComplete: (results: PlotAnalysisResponse) => void;
  onAnalysisError: (error: string) => void;
  onLoadingChange: (loading: boolean) => void;
  onHeatmapLoadingChange: (loading: boolean) => void;
  onClear: () => void;
  enableHeatmap?: boolean;
  isAnalysisLoading?: boolean;
  onShowKMLPanel?: () => void;
}

// Drawing control component that uses the map instance
function DrawControl({ onAnalysisComplete, onAnalysisError, onLoadingChange, onClear, onPolygonChange }: MapProps & { onPolygonChange?: (polygon: GeoJSONPolygon | null) => void }) {
  const map = useMap();
  const drawnItemsRef = useRef<L.FeatureGroup>(new L.FeatureGroup());
  
  useEffect(() => {
    const drawnItems = drawnItemsRef.current;
    map.addLayer(drawnItems);

    // Create draw control
    const drawControl = new L.Control.Draw({
      draw: {
        polyline: false,
        polygon: {
          allowIntersection: false,
          showArea: true,
          drawError: {
            color: '#b00b00',
            timeout: 1000
          }
        },
        circle: false,
        rectangle: {
          showArea: true
        },
        marker: false,
        circlemarker: false
      },
      edit: {
        featureGroup: drawnItems,
        remove: true
      }
    });

    map.addControl(drawControl);

    // Handle drawing completion
    const onDrawCreated = async (e: any) => {
      const { layer } = e;
      // Force clear all existing layers and results before adding new one
      drawnItems.clearLayers();
      onClear(); // Clear previous results immediately
      drawnItems.addLayer(layer);

      try {
        onLoadingChange(true);

        // Convert Leaflet polygon to GeoJSON
        const geoJson = layer.toGeoJSON();
        const geometry: GeoJSONPolygon = {
          type: 'Polygon',
          coordinates: geoJson.geometry.coordinates
        };

        // Notify parent component of polygon change
        onPolygonChange?.(geometry);

        console.log('Analyzing polygon:', geometry);

        // Call the analyze-plot API
        const results = await analyzePlot(geometry);
        console.log('Analysis results:', results);

        onAnalysisComplete(results);
      } catch (error) {
        console.error('Analysis error:', error);
        onAnalysisError(error instanceof Error ? error.message : 'Failed to analyze plot');
      } finally {
        onLoadingChange(false);
      }
    };

    // Handle layer removal
    const onDrawDeleted = (e: any) => {
      // Ensure all layers are properly cleared
      drawnItems.clearLayers();
      onClear();
      onPolygonChange?.(null); // Clear polygon
    };

    const onDrawEdited = async (e: any) => {
      const layers = e.layers;
      layers.eachLayer(async (layer: any) => {
        try {
          onLoadingChange(true);
          onClear();

          const geoJson = layer.toGeoJSON();
          const geometry: GeoJSONPolygon = {
            type: 'Polygon',
            coordinates: geoJson.geometry.coordinates
          };

          // Notify parent component of polygon change
          onPolygonChange?.(geometry);

          const results = await analyzePlot(geometry);
          onAnalysisComplete(results);
        } catch (error) {
          console.error('Analysis error:', error);
          onAnalysisError(error instanceof Error ? error.message : 'Failed to analyze plot');
        } finally {
          onLoadingChange(false);
        }
      });
    };

    // Add event listeners
    map.on(L.Draw.Event.CREATED, onDrawCreated);
    map.on(L.Draw.Event.DELETED, onDrawDeleted);
    map.on(L.Draw.Event.EDITED, onDrawEdited);

    // Cleanup
    return () => {
      map.off(L.Draw.Event.CREATED, onDrawCreated);
      map.off(L.Draw.Event.DELETED, onDrawDeleted);
      map.off(L.Draw.Event.EDITED, onDrawEdited);
      map.removeControl(drawControl);
      map.removeLayer(drawnItems);
    };
  }, [map, onAnalysisComplete, onAnalysisError, onLoadingChange, onClear, onPolygonChange]);

  return null;
}

// Ecoregion layer component
function EcoregionLayer({ visible }: { visible: boolean }) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);
  const [loading, setLoading] = useState(false);

  useMapEvents({
    moveend: () => {
      if (visible) {
        loadEcoregions();
      }
    }
  });

  const loadEcoregions = async () => {
    if (!visible || loading) return;

    const bounds = map.getBounds();
    const bbox = `${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`;

    // Adjust simplification based on zoom level
    const zoom = map.getZoom();
    const simplify = zoom < 5 ? 0.1 : zoom < 8 ? 0.05 : 0.01;

    try {
      setLoading(true);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth'}/api/geospatial/ecoregions/boundaries?bbox=${bbox}&simplify=${simplify}`);
      const data = await response.json();

      // Remove old layer
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
      }

      // Add new layer
      layerRef.current = L.geoJSON(data, {
        style: (feature) => ({
          color: feature?.properties?.color || '#00ff00',
          weight: 1,
          opacity: 0.6,
          fillOpacity: 0.1,
          fillColor: feature?.properties?.color_bio || '#00ff00'
        }),
        onEachFeature: (feature, layer) => {
          layer.bindPopup(`
            <div class="p-2">
              <h3 class="font-semibold">${feature.properties.eco_name}</h3>
              <p class="text-sm">${feature.properties.biome_name}</p>
              <p class="text-xs text-gray-500">${feature.properties.realm}</p>
            </div>
          `);
        }
      });

      layerRef.current.addTo(map);
    } catch (error) {
      console.error('Error loading ecoregions:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      loadEcoregions();
    } else if (layerRef.current) {
      map.removeLayer(layerRef.current);
      layerRef.current = null;
    }

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
      }
    };
  }, [visible]);

  return null;
}

// Intact forest layer component
function IntactForestLayer({ visible, opacity }: { visible: boolean; opacity: number }) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);
  const [loading, setLoading] = useState(false);
  const lastRequestRef = useRef<{ bbox: string; zoom: number } | null>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  useMapEvents({
    moveend: () => {
      if (visible) {
        debouncedLoadIntactForests();
      }
    },
    zoomend: () => {
      if (visible) {
        debouncedLoadIntactForests();
      }
    }
  });

  const debouncedLoadIntactForests = () => {
    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set new timer - wait 300ms after user stops moving/zooming
    debounceTimerRef.current = setTimeout(() => {
      loadIntactForests();
    }, 300);
  };

  const loadIntactForests = async () => {
    if (!visible) return;

    const bounds = map.getBounds();
    const bbox = `${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`;
    const zoom = map.getZoom();

    // Skip if already loading the same request
    if (loading && lastRequestRef.current?.bbox === bbox && lastRequestRef.current?.zoom === zoom) {
      return;
    }

    lastRequestRef.current = { bbox, zoom };

    try {
      setLoading(true);
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth'}/api/geospatial/intact-forests/boundaries?bbox=${bbox}&zoom=${zoom}`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      // Remove old layer
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
      }

      // Add new layer
      layerRef.current = L.geoJSON(data, {
        style: () => ({
          color: '#065f46', // Dark green border
          weight: 1,
          opacity: opacity,
          fillOpacity: opacity * 0.4,
          fillColor: '#10b981' // Emerald green fill
        }),
        onEachFeature: (feature, layer) => {
          const props = feature.properties;
          layer.bindPopup(`
            <div class="p-2">
              <h3 class="font-semibold text-emerald-600">Intact Forest Landscape</h3>
              <p class="text-sm"><strong>Year:</strong> ${props.year}</p>
              <p class="text-sm"><strong>Area:</strong> ${props.area_km2?.toLocaleString()} km²</p>
              <p class="text-xs text-gray-500">ID: ${props.ifl_id}</p>
            </div>
          `);
        }
      });

      layerRef.current.addTo(map);
    } catch (error) {
      console.error('Error loading intact forests:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      loadIntactForests();
    } else if (layerRef.current) {
      map.removeLayer(layerRef.current);
      layerRef.current = null;
      lastRequestRef.current = null;
      // Clear any pending debounce timer
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    }

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
      }
      // Clear debounce timer on unmount
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [visible]);

  // Update opacity when it changes
  useEffect(() => {
    if (layerRef.current && visible) {
      layerRef.current.setStyle({
        opacity: opacity,
        fillOpacity: opacity * 0.4
      });
    }
  }, [opacity, visible]);

  return null;
}

// Smooth interpolated heatmap layer using leaflet.heat
function OccurrenceHeatmapLayer({ visible, opacity, polygon, onHeatmapLoadingChange }: { visible: boolean; opacity: number; polygon?: GeoJSONPolygon | null; onHeatmapLoadingChange?: (loading: boolean) => void }) {
  const map = useMap();
  const heatLayerRef = useRef<any>(null);
  const [loading, setLoading] = useState(false);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  useMapEvents({
    moveend: () => {
      if (visible && polygon) {
        debouncedLoadHeatmap();
      }
    },
    zoomend: () => {
      if (visible && polygon) {
        debouncedLoadHeatmap();
      }
    }
  });

  const debouncedLoadHeatmap = () => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      loadHeatmap();
    }, 300);
  };

  // Helper function to check if a point is inside a polygon
  const isPointInPolygon = (point: [number, number], polygon: GeoJSONPolygon): boolean => {
    if (!polygon || !polygon.coordinates || polygon.coordinates.length === 0) return false;

    const [lng, lat] = point;
    const coords = polygon.coordinates[0]; // Get outer ring

    let inside = false;
    for (let i = 0, j = coords.length - 1; i < coords.length; j = i++) {
      const xi = coords[i][0], yi = coords[i][1];
      const xj = coords[j][0], yj = coords[j][1];

      if (((yi > lat) !== (yj > lat)) && (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi)) {
        inside = !inside;
      }
    }
    return inside;
  };

  // Calculate center point of a polygon
  const getPolygonCenter = (coords: number[][]): [number, number] => {
    let totalLat = 0, totalLng = 0;
    coords.forEach(([lng, lat]) => {
      totalLng += lng;
      totalLat += lat;
    });
    return [totalLng / coords.length, totalLat / coords.length];
  };

  const loadHeatmap = async () => {
    console.log('loadHeatmap called - visible:', visible, 'polygon:', polygon ? 'exists' : 'null');

    if (!visible) {
      console.log('Heatmap not visible, skipping');
      return;
    }

    // ONLY load heatmap if there's a polygon drawn
    if (!polygon) {
      console.log('No polygon drawn - removing heatmap');
      // Remove heatmap if no polygon
      if (heatLayerRef.current) {
        map.removeLayer(heatLayerRef.current);
        heatLayerRef.current = null;
      }
      return;
    }

      console.log('Polygon exists - loading heatmap for polygon bounds');

    const bounds = map.getBounds();
    const minLat = bounds.getSouth();
    const minLng = bounds.getWest();
    const maxLat = bounds.getNorth();
    const maxLng = bounds.getEast();

    try {
      setLoading(true);
      onHeatmapLoadingChange?.(true);
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth'}/api/geospatial/heatmap?minLat=${minLat}&minLng=${minLng}&maxLat=${maxLat}&maxLng=${maxLng}`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      // Remove old layer
      if (heatLayerRef.current) {
        map.removeLayer(heatLayerRef.current);
      }

      // Convert geohash tiles to point cloud with intensity values
      const heatPoints: [number, number, number][] = [];
      let filteredCount = 0;
      let totalCount = 0;
      let maxOccurrences = 0;
      let minOccurrences = Infinity;

      // First pass: find range of occurrences among filtered points
      if (data.features && data.features.length > 0) {
        data.features.forEach((feature: any) => {
          if (!feature.geometry || !feature.geometry.coordinates) return;

          const coords = feature.geometry.coordinates[0]; // Get outer ring
          if (!coords || coords.length === 0) return;

          // Calculate center point of the tile
          const [lng, lat] = getPolygonCenter(coords);

          // ONLY include points within the drawn polygon
          if (!isPointInPolygon([lng, lat], polygon)) {
            return;
          }

          const totalOccurrences = feature.properties?.total_occurrences || 0;
          maxOccurrences = Math.max(maxOccurrences, totalOccurrences);
          minOccurrences = Math.min(minOccurrences, totalOccurrences);
        });

        console.log(`Heatmap data range: min=${minOccurrences}, max=${maxOccurrences}`);

        // Second pass: create heat points with intensity based on total occurrences
        data.features.forEach((feature: any) => {
          totalCount++;
          if (!feature.geometry || !feature.geometry.coordinates) return;

          const coords = feature.geometry.coordinates[0]; // Get outer ring
          if (!coords || coords.length === 0) return;

          // Calculate center point of the tile
          const [lng, lat] = getPolygonCenter(coords);

          // ONLY include points within the drawn polygon
          if (!isPointInPolygon([lng, lat], polygon)) {
            return;
          }

          filteredCount++;

          const totalOccurrences = feature.properties?.total_occurrences || 0;

          // For tiles with multiple occurrences, create multiple points or use logarithmic scaling
          // Use logarithmic scaling to handle wide range of values
          let intensity;
          if (totalOccurrences <= 1) {
            intensity = 0.1; // Minimum intensity for tiles with 1 occurrence
          } else {
            // Logarithmic scaling: log(occurrences) gives us a nice spread
            // Normalize to 0-1 range, then boost high values
            const logIntensity = Math.log(totalOccurrences) / Math.log(maxOccurrences);
            intensity = Math.max(0.1, Math.pow(logIntensity, 0.7)); // Ensure minimum visibility
          }

          // For tiles with many occurrences, add multiple points to create stronger hotspots
          const numPoints = Math.min(totalOccurrences, 10); // Cap at 10 points per tile
          for (let i = 0; i < numPoints; i++) {
            // Add slight random offset to create a cluster effect
            const offsetLat = (Math.random() - 0.5) * 0.001; // Small random offset
            const offsetLng = (Math.random() - 0.5) * 0.001;
            heatPoints.push([lat + offsetLat, lng + offsetLng, intensity]);
          }
        });
      }

      console.log(`Heatmap: ${filteredCount} points inside polygon out of ${totalCount} total tiles`);

      // Create heat layer with smooth gradient
      if (heatPoints.length > 0) {
        heatLayerRef.current = (L as any).heatLayer(heatPoints, {
          radius: 20, // Smaller radius for more precise hotspots
          blur: 12, // Less blur for sharper hotspots
          maxZoom: 17, // Max zoom for heat calculations
          max: 1.0, // Maximum intensity value
          minOpacity: 0.3, // Minimum opacity for visibility
          gradient: {
            0.0: '#3b82f6', // Blue (low density)
            0.2: '#10b981', // Green
            0.4: '#eab308', // Yellow
            0.6: '#f97316', // Orange
            0.8: '#dc2626', // Dark red
            1.0: '#b91c1c'  // Deep red (very high density)
          }
        });

        heatLayerRef.current.setOptions({ opacity: opacity });
        heatLayerRef.current.addTo(map);
      }
    } catch (error) {
      console.error('Error loading heatmap:', error);
    } finally {
      setLoading(false);
      onHeatmapLoadingChange?.(false);
    }
  };

  useEffect(() => {
    if (visible) {
      loadHeatmap();
    } else if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current);
      heatLayerRef.current = null;
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    }

    return () => {
      if (heatLayerRef.current) {
        map.removeLayer(heatLayerRef.current);
      }
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [visible, polygon]);

  // Update opacity when it changes
  useEffect(() => {
    if (heatLayerRef.current && visible) {
      heatLayerRef.current.setOptions({ opacity: opacity });
    }
  }, [opacity, visible]);

  // Add loading indicator to map
  useEffect(() => {
    let control: any = null;

    if (loading) {
      const LoadingControl = L.Control.extend({
        options: {
          position: 'bottomright'
        },
        onAdd: function() {
          const div = L.DomUtil.create('div', 'leaflet-control-heatmap-loading');
          div.style.cssText = `
            background: rgba(0, 0, 0, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 6px;
            padding: 6px 10px;
            display: flex;
            align-items: center;
            gap: 6px;
            backdrop-filter: blur(8px);
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 12px;
            color: white;
            z-index: 1000;
          `;

          div.innerHTML = `
            <div style="
              width: 12px;
              height: 12px;
              border: 2px solid #ef4444;
              border-top-color: transparent;
              border-radius: 50%;
              animation: spin 1s linear infinite;
            "></div>
            <span style="font-weight: 500;">Buffering...</span>
          `;

          // Add CSS animation
          const style = document.createElement('style');
          style.textContent = `
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
            .leaflet-control-heatmap-loading {
              margin-bottom: 10px !important;
              margin-right: 10px !important;
            }
          `;
          div.appendChild(style);

          return div;
        }
      });

      control = new LoadingControl();
      map.addControl(control);
    }

    return () => {
      if (control) {
        map.removeControl(control);
      }
    };
  }, [loading, map]);

  return null;
}

// External polygon display component
function ExternalPolygonLayer({ geometry }: { geometry: GeoJSONPolygon | null }) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);

  useEffect(() => {
    // Remove previous layer
    if (layerRef.current) {
      map.removeLayer(layerRef.current);
      layerRef.current = null;
    }

    // Add new layer if geometry exists
    if (geometry) {
      layerRef.current = L.geoJSON(geometry, {
        style: {
          color: '#3388ff',
          weight: 3,
          opacity: 0.8,
          fillOpacity: 0.2
        }
      });
      
      layerRef.current.addTo(map);
      
      // Fit map to bounds
      const bounds = layerRef.current.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [20, 20] });
      }
    }

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
      }
    };
  }, [map, geometry]);

  return null;
}

// Base layer configurations
const BASE_LAYERS = [
  {
    id: 'osm-standard',
    name: 'OpenStreetMap',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19
  },
  {
    id: 'carto-light',
    name: 'Light (Minimal)',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap © CARTO',
    maxZoom: 20
  },
  {
    id: 'carto-voyager',
    name: 'Light with Terrain',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap © CARTO',
    maxZoom: 20
  },
  {
    id: 'stamen-toner-lite',
    name: 'Toner Lite (B&W)',
    url: 'https://tiles.stadiamaps.com/tiles/stamen_toner_lite/{z}/{x}/{y}{r}.png',
    attribution: '© Stamen Design © OpenStreetMap',
    maxZoom: 20
  },
  {
    id: 'esri-imagery',
    name: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '© ESRI',
    maxZoom: 19
  },
  {
    id: 'stamen-terrain',
    name: 'Terrain (Colorful)',
    url: 'https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}{r}.png',
    attribution: '© Stamen Design © OpenStreetMap',
    maxZoom: 18
  },
  {
    id: 'opentopo',
    name: 'Topographic',
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap © OpenTopoMap',
    maxZoom: 17
  },
  {
    id: 'carto-dark',
    name: 'Dark Mode',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap © CARTO',
    maxZoom: 20
  }
];

// Dynamic TileLayer component
function DynamicTileLayer({ baseLayerId }: { baseLayerId: string }) {
  const map = useMap();
  const layerRef = useRef<L.TileLayer | null>(null);

  useEffect(() => {
    // Remove old layer
    if (layerRef.current) {
      map.removeLayer(layerRef.current);
    }

    // Find and add new layer
    const layerConfig = BASE_LAYERS.find(l => l.id === baseLayerId);
    if (layerConfig) {
      layerRef.current = L.tileLayer(layerConfig.url, {
        attribution: layerConfig.attribution,
        maxZoom: layerConfig.maxZoom
      });
      layerRef.current.addTo(map);
    }

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
      }
    };
  }, [map, baseLayerId]);

  return null;
}

export default function Map({ onAnalysisComplete, onAnalysisError, onLoadingChange, onHeatmapLoadingChange, onClear, enableHeatmap, isAnalysisLoading, onShowKMLPanel }: MapProps) {
  const [externalGeometry, setExternalGeometry] = useState<GeoJSONPolygon | null>(null);
  const [drawnPolygon, setDrawnPolygon] = useState<GeoJSONPolygon | null>(null);
  const [isHeatmapLoading, setIsHeatmapLoading] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);
  const [baseLayer, setBaseLayer] = useState<string>('carto-dark');
  const [overlayLayer, setOverlayLayer] = useState<'none' | 'ecoregions' | 'intact-forests' | 'heatmap'>('none');
  const [layerOpacity, setLayerOpacity] = useState(0.6);

  // Auto-enable heatmap when enableHeatmap prop is true
  useEffect(() => {
    if (enableHeatmap) {
      setOverlayLayer('heatmap');
    }
  }, [enableHeatmap]);

  // Handle polygon changes from drawing
  const handlePolygonChange = (polygon: GeoJSONPolygon | null) => {
    setDrawnPolygon(polygon);
  };

  // Handle heatmap loading changes
  const handleHeatmapLoadingChange = (loading: boolean) => {
    setIsHeatmapLoading(loading);
    onHeatmapLoadingChange?.(loading);
  };

  // Function to handle externally provided geometry (from KML upload)
  const handleExternalGeometry = async (geometry: GeoJSONPolygon) => {
    try {
      onLoadingChange(true);
      onClear();

      setExternalGeometry(geometry);
      setDrawnPolygon(geometry); // Also set as drawn polygon for heatmap filtering

      const results = await analyzePlot(geometry);
      onAnalysisComplete(results);
    } catch (error) {
      console.error('Analysis error:', error);
      onAnalysisError(error instanceof Error ? error.message : 'Failed to analyze plot');
    } finally {
      onLoadingChange(false);
    }
  };

  return (
    <div className="h-full w-full relative">
      <MapContainer
        center={[20, 0]} // Global view center
        zoom={2} // World-level zoom
        style={{ height: '100%', width: '100%' }}
        className="z-0"
      >
        <DynamicTileLayer baseLayerId={baseLayer} />

        <DrawControl
          onAnalysisComplete={onAnalysisComplete}
          onAnalysisError={onAnalysisError}
          onLoadingChange={onLoadingChange}
          onClear={onClear}
          onPolygonChange={handlePolygonChange}
        />

        <ExternalPolygonLayer geometry={externalGeometry} />

        <EcoregionLayer visible={overlayLayer === 'ecoregions'} />
        <IntactForestLayer visible={overlayLayer === 'intact-forests'} opacity={layerOpacity} />
        <OccurrenceHeatmapLayer visible={overlayLayer === 'heatmap'} opacity={layerOpacity} polygon={drawnPolygon} onHeatmapLoadingChange={handleHeatmapLoadingChange} />
      </MapContainer>

      {/* Loading overlays */}
      {isAnalysisLoading && (
        <div className="absolute inset-0 bg-black/30 backdrop-blur-md flex items-center justify-center z-[2000]">
          <div className="bg-black/90 backdrop-blur-md border border-white/20 rounded-xl shadow-2xl p-6 flex items-center gap-4">
            <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
            <div>
              <div className="text-white font-semibold text-lg">
                Analyzing Tree Occurrence Data
              </div>
              <div className="text-white/70 text-sm">
                Processing species data within your polygon...
              </div>
            </div>
          </div>
        </div>
      )}

      {/* KML Upload Button - Show when no polygon is drawn */}
      {!drawnPolygon && !isAnalysisLoading && (
        <div className="absolute top-4 left-4 z-[1000]">
          <button
            onClick={onShowKMLPanel}
            className="bg-black/80 backdrop-blur-md border border-white/20 rounded-lg px-4 py-2 text-white text-sm hover:bg-black/90 transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            Upload KML
          </button>
        </div>
      )}

      {/* Heatmap Buffering Indicator */}
      {isHeatmapLoading && (
        <div className="absolute bottom-4 right-4 z-[1000]">
          <div className="bg-black/85 backdrop-blur-md border border-white/20 rounded-lg px-3 py-2 flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-red-500 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-white text-sm font-medium">Buffering...</span>
          </div>
        </div>
      )}

      {/* Layer control panel */}
      <div className="absolute top-4 right-4 z-10 space-y-2">
        <div className="bg-black/80 backdrop-blur-md border border-white/20 rounded-xl shadow-lg p-3 min-w-[200px]">
          <div className="flex items-center gap-2 mb-3">
            <Layers className="w-5 h-5 text-emerald-300" />
            <span className="text-sm font-medium text-white">Map Layers</span>
          </div>

          {/* Base Layer Section */}
          <div className="mb-3">
            <label className="text-xs text-white/60 mb-1.5 block uppercase tracking-wider">
              Base View
            </label>
            <select
              value={baseLayer}
              onChange={(e) => setBaseLayer(e.target.value)}
              className="w-full bg-black/50 border border-white/20 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-emerald-500 transition-colors"
            >
              {BASE_LAYERS.map(layer => (
                <option key={layer.id} value={layer.id}>
                  {layer.name}
                </option>
              ))}
            </select>
          </div>

          {/* Overlay Layer Section */}
          <div>
            <label className="text-xs text-white/60 mb-1.5 block uppercase tracking-wider">
              Overlay Layers
            </label>
            <select
              value={overlayLayer}
              onChange={(e) => setOverlayLayer(e.target.value as 'none' | 'ecoregions' | 'intact-forests' | 'heatmap')}
              className="w-full bg-black/50 border border-white/20 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-emerald-500 transition-colors"
            >
              <option value="none">None</option>
              <option value="ecoregions">Ecoregions</option>
              <option value="intact-forests">Intact Forests</option>
              <option value="heatmap">Occurrence Heatmap</option>
            </select>

            {overlayLayer !== 'none' && (
              <div className="mt-3">
                <label className="text-xs text-white/80 mb-1 block">
                  Opacity: {Math.round(layerOpacity * 100)}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={layerOpacity}
                  onChange={(e) => setLayerOpacity(parseFloat(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Collapsible instructions overlay */}
      <div className="absolute bottom-4 left-4 z-10">
        {showInstructions ? (
          <div className="bg-black/80 backdrop-blur-md border border-white/20 rounded-xl shadow-lg p-4 max-w-sm">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-emerald-300">How to use:</h3>
              <button
                onClick={() => setShowInstructions(false)}
                className="text-white/60 hover:text-white transition-colors"
                aria-label="Minimize instructions"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
            <ul className="text-sm text-white/80 space-y-1">
              <li>• Use the polygon tool to draw an area</li>
              <li>• Use the rectangle tool for simple rectangular areas</li>
              <li>• Edit or delete drawn shapes using the edit tools</li>
              <li>• Or upload a KML file in the sidebar</li>
            </ul>
          </div>
        ) : (
          <button
            onClick={() => setShowInstructions(true)}
            className="bg-black/80 backdrop-blur-md border border-white/20 rounded-xl shadow-lg p-3 text-emerald-300 hover:text-emerald-200 transition-colors"
            aria-label="Show instructions"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

// External geometry handler is handled internally within the component