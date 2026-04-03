'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import {
  X, Loader2, MapPin, ChevronDown, ChevronRight,
  Layers, Play, Pause, BarChart3, Grid3X3
} from 'lucide-react';
import { GeoJSONPolygon } from '@/lib/types';

// ─── Types ────────────────────────────────────────────────────────────────

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
  sections: Record<string, SiteSection>;
}

interface TileResult {
  lat: number;
  lon: number;
  data: SiteContextResponse;
  rectangle?: L.Rectangle;
}

interface RunningStats {
  count: number;
  mean: number;
  m2: number;     // for Welford's variance
  min: number;
  max: number;
}

interface ClusterInfo {
  id: number;
  count: number;
  centroid: number[];
  color: string;
}

interface AreaSiteInspectorProps {
  polygon: GeoJSONPolygon;
  onClose: () => void;
}

// ─── Constants ────────────────────────────────────────────────────────────

const CONCURRENCY = 5;

const COLORABLE_VARIABLES: { key: string; label: string; section: string; continuous: boolean }[] = [
  { key: 'annual_mean_temp', label: 'Temperature', section: 'climate_water', continuous: true },
  { key: 'annual_precip', label: 'Precipitation', section: 'climate_water', continuous: true },
  { key: 'aridity_index', label: 'Aridity Index', section: 'climate_water', continuous: true },
  { key: 'elevation', label: 'Elevation', section: 'terrain_soil', continuous: true },
  { key: 'slope', label: 'Slope', section: 'terrain_soil', continuous: true },
  { key: 'soil_ph', label: 'Soil pH', section: 'terrain_soil', continuous: true },
  { key: 'canopy_height', label: 'Canopy Height', section: 'carbon_productivity', continuous: true },
  { key: 'biomass_agb', label: 'Biomass', section: 'carbon_productivity', continuous: true },
  { key: 'gpp', label: 'Productivity', section: 'carbon_productivity', continuous: true },
  { key: 'human_modification', label: 'Human Modification', section: 'land_state', continuous: true },
  { key: 'neumann_natural', label: 'Natural Forest Prob.', section: 'land_state', continuous: true },
  { key: 'fire_frequency', label: 'Fire Frequency', section: 'land_state', continuous: true },
  { key: 'esa_worldcover', label: 'Land Cover', section: 'land_state', continuous: false },
  { key: 'dynamic_world', label: 'Land Use', section: 'land_state', continuous: false },
  { key: 'xiao_planted', label: 'Forest Origin', section: 'land_state', continuous: false },
];

const CLUSTER_COLORS = [
  '#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16'
];

// ─── Utility functions ────────────────────────────────────────────────────

function pointInPolygon(lat: number, lon: number, polygon: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][1], yi = polygon[i][0]; // GeoJSON is [lng, lat]
    const xj = polygon[j][1], yj = polygon[j][0];
    const intersect = ((yi > lon) !== (yj > lon)) &&
      (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function getPolygonExtentKm(polygon: GeoJSONPolygon): number {
  const ring = polygon.coordinates[0];
  if (!ring || ring.length < 3) return 0;
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  for (const [lon, lat] of ring) {
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
  }
  const latKm = (maxLat - minLat) * 111.32;
  const centerLat = (minLat + maxLat) / 2;
  const lonKm = (maxLon - minLon) * 111.32 * Math.cos(centerLat * Math.PI / 180);
  return Math.max(latKm, lonKm);
}

function suggestTileSize(polygon: GeoJSONPolygon): number {
  const extent = getPolygonExtentKm(polygon);
  // Target ~30-80 tiles: size ≈ extent / 7
  if (extent < 0.5) return 0.05;
  if (extent < 2) return 0.2;
  if (extent < 10) return 0.5;
  if (extent < 50) return 2;
  return 5;
}

function generateGridPoints(polygon: GeoJSONPolygon, tileSize: number): { lat: number; lon: number }[] {
  const ring = polygon.coordinates[0]; // outer ring
  if (!ring || ring.length < 3) return [];

  // Bounding box
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  for (const [lon, lat] of ring) {
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
  }

  // tileSize is in km — convert to degrees
  const latStep = tileSize / 111.32;
  const centerLat = (minLat + maxLat) / 2;
  const lonStep = tileSize / (111.32 * Math.cos(centerLat * Math.PI / 180));

  // Safety: cap at 500 tiles
  const estCols = Math.ceil((maxLon - minLon) / lonStep);
  const estRows = Math.ceil((maxLat - minLat) / latStep);
  if (estCols * estRows > 500) {
    console.warn(`Grid too large (${estCols}x${estRows}), capping. Increase tile size.`);
  }

  const points: { lat: number; lon: number }[] = [];
  let count = 0;
  for (let lat = minLat + latStep / 2; lat < maxLat; lat += latStep) {
    for (let lon = minLon + lonStep / 2; lon < maxLon; lon += lonStep) {
      if (count >= 500) break;
      if (pointInPolygon(lat, lon, ring)) {
        points.push({ lat: Math.round(lat * 10000) / 10000, lon: Math.round(lon * 10000) / 10000 });
        count++;
      }
    }
    if (count >= 500) break;
  }
  return points;
}

function getFieldValue(data: SiteContextResponse, key: string): number | null {
  for (const section of Object.values(data.sections)) {
    if (!section?.fields) continue;
    for (const field of section.fields) {
      if (field.key === key) {
        return typeof field.value === 'number' ? field.value : null;
      }
    }
  }
  return null;
}

function valueToColor(value: number, min: number, max: number): string {
  if (max === min) return '#3b82f6';
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));
  // Blue → Cyan → Green → Yellow → Red
  if (t < 0.25) {
    const s = t / 0.25;
    return `rgb(${Math.round(59 * (1 - s))}, ${Math.round(130 + 70 * s)}, ${Math.round(246 * (1 - s) + 200 * s)})`;
  } else if (t < 0.5) {
    const s = (t - 0.25) / 0.25;
    return `rgb(${Math.round(34 * (1 - s))}, ${Math.round(200 - 3 * s)}, ${Math.round(200 * (1 - s) + 80 * s)})`;
  } else if (t < 0.75) {
    const s = (t - 0.5) / 0.25;
    return `rgb(${Math.round(197 * s)}, ${Math.round(197 + 30 * s)}, ${Math.round(80 * (1 - s))})`;
  } else {
    const s = (t - 0.75) / 0.25;
    return `rgb(${Math.round(197 + 42 * s)}, ${Math.round(227 * (1 - s) + 68 * s)}, ${Math.round(68 * (1 - s))})`;
  }
}

// Simple k-means for clustering tiles
function kMeansClusters(tiles: TileResult[], featureKeys: string[], k: number): Map<number, number> {
  const vectors: number[][] = [];
  const validIndices: number[] = [];

  // Build feature vectors
  tiles.forEach((tile, idx) => {
    const vec: number[] = [];
    let valid = true;
    for (const key of featureKeys) {
      const val = getFieldValue(tile.data, key);
      if (val === null) { valid = false; break; }
      vec.push(val);
    }
    if (valid) {
      vectors.push(vec);
      validIndices.push(idx);
    }
  });

  if (vectors.length < k) return new Map();

  // Normalize features (z-score)
  const dims = featureKeys.length;
  const means: number[] = new Array(dims).fill(0);
  const stds: number[] = new Array(dims).fill(0);
  for (const vec of vectors) {
    for (let d = 0; d < dims; d++) means[d] += vec[d];
  }
  for (let d = 0; d < dims; d++) means[d] /= vectors.length;
  for (const vec of vectors) {
    for (let d = 0; d < dims; d++) stds[d] += (vec[d] - means[d]) ** 2;
  }
  for (let d = 0; d < dims; d++) stds[d] = Math.sqrt(stds[d] / vectors.length) || 1;

  const normalized = vectors.map(vec => vec.map((v, d) => (v - means[d]) / stds[d]));

  // Initialize centroids (k-means++ simplified: pick first random, rest by max distance)
  const centroids: number[][] = [];
  centroids.push([...normalized[Math.floor(Math.random() * normalized.length)]]);
  for (let c = 1; c < k; c++) {
    let maxDist = -1, bestIdx = 0;
    for (let i = 0; i < normalized.length; i++) {
      let minCentDist = Infinity;
      for (const cent of centroids) {
        let dist = 0;
        for (let d = 0; d < dims; d++) dist += (normalized[i][d] - cent[d]) ** 2;
        minCentDist = Math.min(minCentDist, dist);
      }
      if (minCentDist > maxDist) { maxDist = minCentDist; bestIdx = i; }
    }
    centroids.push([...normalized[bestIdx]]);
  }

  // Lloyd's iterations
  const assignments = new Array(normalized.length).fill(0);
  for (let iter = 0; iter < 20; iter++) {
    // Assign
    let changed = false;
    for (let i = 0; i < normalized.length; i++) {
      let bestC = 0, bestDist = Infinity;
      for (let c = 0; c < k; c++) {
        let dist = 0;
        for (let d = 0; d < dims; d++) dist += (normalized[i][d] - centroids[c][d]) ** 2;
        if (dist < bestDist) { bestDist = dist; bestC = c; }
      }
      if (assignments[i] !== bestC) { assignments[i] = bestC; changed = true; }
    }
    if (!changed) break;

    // Update centroids
    const counts = new Array(k).fill(0);
    const sums = centroids.map(() => new Array(dims).fill(0));
    for (let i = 0; i < normalized.length; i++) {
      counts[assignments[i]]++;
      for (let d = 0; d < dims; d++) sums[assignments[i]][d] += normalized[i][d];
    }
    for (let c = 0; c < k; c++) {
      if (counts[c] > 0) {
        for (let d = 0; d < dims; d++) centroids[c][d] = sums[c][d] / counts[c];
      }
    }
  }

  // Map original tile index → cluster
  const result = new Map<number, number>();
  for (let i = 0; i < validIndices.length; i++) {
    result.set(validIndices[i], assignments[i]);
  }
  return result;
}

// ─── Component ────────────────────────────────────────────────────────────

export default function AreaSiteInspector({ polygon, onClose }: AreaSiteInspectorProps) {
  const map = useMap();
  const [status, setStatus] = useState<'config' | 'sampling' | 'paused' | 'complete' | 'error'>('config');
  const [tileSize, setTileSize] = useState(0.5); // km
  const [gridPoints, setGridPoints] = useState<{ lat: number; lon: number }[]>([]);
  const [tiles, setTiles] = useState<TileResult[]>([]);
  const [completedCount, setCompletedCount] = useState(0);
  const [failedCount, setFailedCount] = useState(0);
  const [colorVariable, setColorVariable] = useState('annual_mean_temp');
  const [showClusters, setShowClusters] = useState(false);
  const [clusterCount, setClusterCount] = useState(3);
  const [clusterAssignments, setClusterAssignments] = useState<Map<number, number>>(new Map());
  const [stats, setStats] = useState<Record<string, RunningStats>>({});
  const [elapsedTime, setElapsedTime] = useState(0);
  const [expandedPanel, setExpandedPanel] = useState(true);

  const abortRef = useRef<AbortController | null>(null);
  const tilesRef = useRef<TileResult[]>([]);
  const layerGroupRef = useRef<L.LayerGroup>(L.layerGroup());
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const statsRef = useRef<Record<string, RunningStats>>({});
  const isPausedRef = useRef(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Prevent Leaflet from capturing mouse events on the panel
  useEffect(() => {
    const el = panelRef.current;
    if (el) {
      L.DomEvent.disableClickPropagation(el);
      L.DomEvent.disableScrollPropagation(el);
    }
  }, []);

  // Generate grid on config
  useEffect(() => {
    console.log('AreaSiteInspector polygon:', JSON.stringify(polygon).slice(0, 200));
    console.log('AreaSiteInspector tileSize:', tileSize);
    const points = generateGridPoints(polygon, tileSize);
    console.log('AreaSiteInspector generated', points.length, 'grid points');
    setGridPoints(points);
  }, [polygon, tileSize]);

  // Add/remove layer group from map
  useEffect(() => {
    layerGroupRef.current.addTo(map);
    return () => {
      layerGroupRef.current.clearLayers();
      map.removeLayer(layerGroupRef.current);
    };
  }, [map]);

  // Recolor tiles when variable or cluster mode changes
  useEffect(() => {
    recolorTiles();
  }, [colorVariable, showClusters, clusterAssignments]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const recolorTiles = useCallback(() => {
    const currentTiles = tilesRef.current;
    if (currentTiles.length === 0) return;

    const varDef = COLORABLE_VARIABLES.find(v => v.key === colorVariable);
    if (!varDef) return;

    if (showClusters && clusterAssignments.size > 0) {
      // Color by cluster
      currentTiles.forEach((tile, idx) => {
        if (!tile.rectangle) return;
        const cluster = clusterAssignments.get(idx);
        const color = cluster !== undefined ? CLUSTER_COLORS[cluster % CLUSTER_COLORS.length] : '#666';
        tile.rectangle.setStyle({ fillColor: color, fillOpacity: 0.6, color: color, weight: 1, opacity: 0.8 });
      });
      return;
    }

    if (varDef.continuous) {
      // Compute min/max for this variable across all tiles
      let min = Infinity, max = -Infinity;
      for (const tile of currentTiles) {
        const val = getFieldValue(tile.data, colorVariable);
        if (val !== null) { min = Math.min(min, val); max = Math.max(max, val); }
      }
      // Color by value
      currentTiles.forEach(tile => {
        if (!tile.rectangle) return;
        const val = getFieldValue(tile.data, colorVariable);
        if (val !== null) {
          const color = valueToColor(val, min, max);
          tile.rectangle.setStyle({ fillColor: color, fillOpacity: 0.6, color, weight: 1, opacity: 0.8 });
        }
      });
    } else {
      // Categorical — assign distinct colors per value
      const categories = new Map<string, string>();
      let colorIdx = 0;
      currentTiles.forEach(tile => {
        if (!tile.rectangle) return;
        for (const section of Object.values(tile.data.sections)) {
          if (!section?.fields) continue;
          for (const field of section.fields) {
            if (field.key === colorVariable) {
              const key = String(field.value);
              if (!categories.has(key)) {
                categories.set(key, CLUSTER_COLORS[colorIdx++ % CLUSTER_COLORS.length]);
              }
              const color = categories.get(key)!;
              tile.rectangle.setStyle({ fillColor: color, fillOpacity: 0.6, color, weight: 1, opacity: 0.8 });
            }
          }
        }
      });
    }
  }, [colorVariable, showClusters, clusterAssignments]);

  const updateStats = (data: SiteContextResponse) => {
    for (const section of Object.values(data.sections)) {
      if (!section?.fields) continue;
      for (const field of section.fields) {
        if (typeof field.value !== 'number') continue;
        const key = field.key;
        const val = field.value;
        if (!statsRef.current[key]) {
          statsRef.current[key] = { count: 0, mean: 0, m2: 0, min: Infinity, max: -Infinity };
        }
        const s = statsRef.current[key];
        s.count++;
        const delta = val - s.mean;
        s.mean += delta / s.count;
        s.m2 += delta * (val - s.mean);
        s.min = Math.min(s.min, val);
        s.max = Math.max(s.max, val);
      }
    }
    setStats({ ...statsRef.current });
  };

  const startSampling = async () => {
    const points = generateGridPoints(polygon, tileSize);
    setGridPoints(points);
    setTiles([]);
    tilesRef.current = [];
    setCompletedCount(0);
    setFailedCount(0);
    setStatus('sampling');
    setShowClusters(false);
    setClusterAssignments(new Map());
    statsRef.current = {};
    setStats({});
    isPausedRef.current = false;
    layerGroupRef.current.clearLayers();

    const controller = new AbortController();
    abortRef.current = controller;

    // Start timer
    const startTime = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedTime(Math.round((Date.now() - startTime) / 1000));
    }, 1000);

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';

    // Tile dimensions for rectangles
    const latStep = tileSize / 111.32;
    const centerLat = points.length > 0 ? points.reduce((s, p) => s + p.lat, 0) / points.length : 0;
    const lonStep = tileSize / (111.32 * Math.cos(centerLat * Math.PI / 180));

    // Semaphore-based concurrency
    let nextIdx = 0;
    let completed = 0;
    let failed = 0;

    const processNext = async (): Promise<void> => {
      while (nextIdx < points.length) {
        // Check pause
        while (isPausedRef.current) {
          await new Promise(r => setTimeout(r, 200));
          if (controller.signal.aborted) return;
        }

        if (controller.signal.aborted) return;
        const idx = nextIdx++;
        const point = points[idx];

        try {
          const response = await fetch(
            `${API_URL}/api/prediction/site-context?lat=${point.lat}&lon=${point.lon}`,
            { signal: controller.signal }
          );

          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const data: SiteContextResponse = await response.json();
          if (!data.success) throw new Error('Sampling failed');

          // Create rectangle
          const bounds: L.LatLngBoundsExpression = [
            [point.lat - latStep / 2, point.lon - lonStep / 2],
            [point.lat + latStep / 2, point.lon + lonStep / 2]
          ];
          const rect = L.rectangle(bounds, {
            fillColor: '#3b82f6',
            fillOpacity: 0.5,
            color: '#3b82f6',
            weight: 1,
            opacity: 0.6
          });

          // Tooltip with key values
          const tempField = data.sections?.climate_water?.fields?.find(f => f.key === 'annual_mean_temp');
          const elevField = data.sections?.terrain_soil?.fields?.find(f => f.key === 'elevation');
          const tooltipLines = [`${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}`];
          if (tempField) tooltipLines.push(`${tempField.value}${tempField.unit}`);
          if (elevField) tooltipLines.push(`${elevField.value}${elevField.unit}`);
          rect.bindTooltip(tooltipLines.join(' | '), { sticky: true, className: 'env-tile-tooltip' });

          rect.addTo(layerGroupRef.current);

          const tile: TileResult = { lat: point.lat, lon: point.lon, data, rectangle: rect };
          tilesRef.current.push(tile);

          completed++;
          setCompletedCount(completed);
          updateStats(data);

          // Recolor every few tiles for performance
          if (completed % 3 === 0 || completed === points.length) {
            recolorTiles();
          }
        } catch (err: any) {
          if (err.name === 'AbortError') return;
          console.error(`Tile ${idx} failed:`, err.message);
          failed++;
          setFailedCount(failed);
        }
      }
    };

    // Launch concurrent workers
    const workers = Array.from({ length: Math.min(CONCURRENCY, points.length) }, () => processNext());
    await Promise.all(workers);

    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (!controller.signal.aborted) {
      setStatus('complete');
      recolorTiles();
    }
  };

  const togglePause = () => {
    if (status === 'sampling') {
      isPausedRef.current = true;
      setStatus('paused');
    } else if (status === 'paused') {
      isPausedRef.current = false;
      setStatus('sampling');
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setStatus('complete');
    recolorTiles();
  };

  const runClustering = () => {
    const featureKeys = COLORABLE_VARIABLES.filter(v => v.continuous).map(v => v.key);
    const assignments = kMeansClusters(tilesRef.current, featureKeys, clusterCount);
    setClusterAssignments(assignments);
    setShowClusters(true);
  };

  const totalPoints = gridPoints.length;
  const progress = totalPoints > 0 ? Math.round((completedCount / totalPoints) * 100) : 0;

  // Get current variable stats
  const currentStats = stats[colorVariable];
  const currentVarDef = COLORABLE_VARIABLES.find(v => v.key === colorVariable);

  return (
    <div ref={panelRef} className="absolute top-4 left-4 z-[1001] w-80">
      <div className="bg-gray-950/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-900/80 to-gray-900/80 px-4 py-3 border-b border-white/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Grid3X3 className="h-5 w-5 text-blue-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">Area Site Inspector</h3>
                <p className="text-xs text-white/50">{totalPoints} tiles at {tileSize}km spacing</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => setExpandedPanel(!expandedPanel)} className="text-white/40 hover:text-white p-1">
                {expandedPanel ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              <button onClick={() => { handleStop(); onClose(); }} className="text-white/40 hover:text-white p-1">
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {expandedPanel && (
          <div className="p-3 space-y-3 max-h-[70vh] overflow-y-auto">
            {/* Config — show before sampling starts */}
            {status === 'config' && (
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-white/60 block mb-1">Tile Spacing</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="range" min="0.1" max="5" step="0.1" value={tileSize}
                      onChange={e => setTileSize(parseFloat(e.target.value))}
                      className="flex-1 accent-blue-500"
                    />
                    <span className="text-sm text-white font-mono w-14 text-right">{tileSize} km</span>
                  </div>
                  <p className="text-xs text-white/40 mt-1">
                    {totalPoints} sample points • ~{Math.round(totalPoints * 8 / 60)} min estimated
                  </p>
                  {totalPoints > 200 && (
                    <p className="text-xs text-yellow-400/80 mt-1">
                      Large area — consider increasing tile spacing for faster results
                    </p>
                  )}
                </div>

                <button
                  onClick={startSampling}
                  disabled={totalPoints === 0}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white rounded-lg transition-colors font-medium text-sm flex items-center justify-center gap-2"
                >
                  <Play className="h-4 w-4" />
                  Start Sampling ({totalPoints} tiles)
                </button>
              </div>
            )}

            {/* Progress */}
            {(status === 'sampling' || status === 'paused') && (
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-blue-300">
                    {status === 'paused' ? 'Paused' : 'Sampling...'}
                    {elapsedTime > 0 && <span className="text-white/40 ml-1">({elapsedTime}s)</span>}
                  </span>
                  <span className="text-blue-400 font-medium">{completedCount}/{totalPoints} ({progress}%)</span>
                </div>
                <div className="h-2 bg-gray-900 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-600 to-blue-400 transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                {failedCount > 0 && (
                  <p className="text-xs text-red-400/70">{failedCount} tiles failed</p>
                )}

                <div className="flex gap-2">
                  <button
                    onClick={togglePause}
                    className="flex-1 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg text-xs flex items-center justify-center gap-1"
                  >
                    {status === 'paused' ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
                    {status === 'paused' ? 'Resume' : 'Pause'}
                  </button>
                  <button
                    onClick={handleStop}
                    className="flex-1 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg text-xs"
                  >
                    Stop & View
                  </button>
                </div>
              </div>
            )}

            {/* Variable selector — show during/after sampling */}
            {(status !== 'config') && completedCount > 0 && (
              <>
                <div>
                  <label className="text-xs text-white/60 block mb-1">Color by</label>
                  <select
                    value={colorVariable}
                    onChange={e => { setColorVariable(e.target.value); setShowClusters(false); }}
                    className="w-full bg-black/50 border border-white/20 rounded-lg px-2 py-1.5 text-white text-xs focus:outline-none focus:border-blue-500"
                  >
                    {COLORABLE_VARIABLES.map(v => (
                      <option key={v.key} value={v.key}>{v.label}</option>
                    ))}
                  </select>
                </div>

                {/* Running stats for selected variable */}
                {currentStats && currentVarDef?.continuous && (
                  <div className="bg-black/30 rounded-lg p-2 border border-white/10">
                    <div className="grid grid-cols-4 gap-1 text-center">
                      <div>
                        <div className="text-[10px] text-white/40">Min</div>
                        <div className="text-xs text-white font-mono">{currentStats.min.toFixed(1)}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-white/40">Mean</div>
                        <div className="text-xs text-white font-mono">{currentStats.mean.toFixed(1)}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-white/40">Max</div>
                        <div className="text-xs text-white font-mono">{currentStats.max.toFixed(1)}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-white/40">StdDev</div>
                        <div className="text-xs text-white font-mono">
                          {currentStats.count > 1 ? Math.sqrt(currentStats.m2 / (currentStats.count - 1)).toFixed(1) : '—'}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Clustering — show when complete */}
            {status === 'complete' && completedCount >= 3 && (
              <div className="border-t border-white/10 pt-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <BarChart3 className="h-3.5 w-3.5 text-purple-400" />
                    <span className="text-xs text-white/70 font-medium">Stratification</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 mb-2">
                  <label className="text-xs text-white/50">Clusters:</label>
                  <input
                    type="range" min="2" max={Math.min(10, completedCount)} step="1" value={clusterCount}
                    onChange={e => setClusterCount(parseInt(e.target.value))}
                    className="flex-1 accent-purple-500"
                  />
                  <span className="text-xs text-white font-mono w-4">{clusterCount}</span>
                </div>

                <button
                  onClick={runClustering}
                  className="w-full py-1.5 bg-purple-600/30 hover:bg-purple-600/50 border border-purple-500/30 text-purple-300 rounded-lg text-xs transition-colors"
                >
                  {showClusters ? 'Re-cluster' : 'Run Clustering'}
                </button>

                {showClusters && (
                  <div className="mt-2 space-y-1">
                    {Array.from(new Set(clusterAssignments.values())).sort().map(clusterId => {
                      const count = Array.from(clusterAssignments.values()).filter(c => c === clusterId).length;
                      return (
                        <div key={clusterId} className="flex items-center gap-2 text-xs">
                          <div
                            className="w-3 h-3 rounded-sm"
                            style={{ backgroundColor: CLUSTER_COLORS[clusterId % CLUSTER_COLORS.length] }}
                          />
                          <span className="text-white/70">Cluster {clusterId + 1}</span>
                          <span className="text-white/40 ml-auto">{count} tiles</span>
                        </div>
                      );
                    })}
                    <button
                      onClick={() => { setShowClusters(false); recolorTiles(); }}
                      className="w-full py-1 text-xs text-white/40 hover:text-white/60"
                    >
                      Back to variable view
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Completion summary */}
            {status === 'complete' && (
              <div className="text-xs text-white/40 text-center pt-1 border-t border-white/10">
                {completedCount} tiles sampled in {elapsedTime}s
                {failedCount > 0 && ` (${failedCount} failed)`}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
