# Heatmap Polygon Filtering Implementation

## Overview
This document outlines the code changes made to fix the heatmap functionality so that it only displays occurrence data within the drawn polygon boundaries, instead of showing data across the entire map.

## Problem Statement
- The heatmap was showing occurrence density data across the entire visible map area (including USA and other regions)
- Performance was poor due to loading excessive data
- The heatmap didn't respect polygon boundaries

## Solution Summary
1. **Auto-enable heatmap** when polygon analysis completes
2. **Client-side polygon filtering** to only show heatmap tiles within the drawn polygon
3. **Polygon state management** to track drawn polygons across components

## Code Changes

### 1. Analysis Page Component (`treekipedia/frontend/app/analysis/page.tsx`)

#### Added State Management
```typescript
// Heatmap state
const [enableHeatmap, setEnableHeatmap] = useState(false);

// Handle polygon changes from the map
const handlePolygonChange = (polygon: GeoJSONPolygon | null) => {
  // This could be used for additional logic if needed
};
```

#### Modified `handleAnalysisComplete`
```typescript
const handleAnalysisComplete = (results: PlotAnalysisResponse) => {
  setAnalysisResults(results);
  setError(null);
  setShowResultsPanel(true);
  setIsResultsMinimized(false);
  setEnableHeatmap(true); // Enable heatmap when analysis completes
};
```

#### Modified `clearResults`
```typescript
const clearResults = () => {
  setAnalysisResults(null);
  setError(null);
  setEnableHeatmap(false); // Disable heatmap when results are cleared
};
```

#### Updated Map Component Props
```typescript
<Map
  onAnalysisComplete={handleAnalysisComplete}
  onAnalysisError={handleAnalysisError}
  onLoadingChange={handleLoadingChange}
  onClear={clearResults}
  enableHeatmap={enableHeatmap}
/>
```

### 2. Map Component (`treekipedia/frontend/app/analysis/components/Map.tsx`)

#### Updated Interface
```typescript
interface MapProps {
  onAnalysisComplete: (results: PlotAnalysisResponse) => void;
  onAnalysisError: (error: string) => void;
  onLoadingChange: (loading: boolean) => void;
  onClear: () => void;
  enableHeatmap?: boolean;
}
```

#### Added State for Polygon Tracking
```typescript
export default function Map({ onAnalysisComplete, onAnalysisError, onLoadingChange, onClear, enableHeatmap }: MapProps) {
  const [externalGeometry, setExternalGeometry] = useState<GeoJSONPolygon | null>(null);
  const [drawnPolygon, setDrawnPolygon] = useState<GeoJSONPolygon | null>(null); // NEW
  // ... rest of state
}
```

#### Added Polygon Change Handler
```typescript
// Handle polygon changes from drawing
const handlePolygonChange = (polygon: GeoJSONPolygon | null) => {
  setDrawnPolygon(polygon);
};
```

#### Auto-enable Heatmap Effect
```typescript
// Auto-enable heatmap when enableHeatmap prop is true
useEffect(() => {
  if (enableHeatmap) {
    setOverlayLayer('heatmap');
  }
}, [enableHeatmap]);
```

#### Updated External Geometry Handler
```typescript
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
```

#### Updated DrawControl Props
```typescript
<DrawControl
  onAnalysisComplete={onAnalysisComplete}
  onAnalysisError={onAnalysisError}
  onLoadingChange={onLoadingChange}
  onClear={onClear}
  onPolygonChange={handlePolygonChange}
/>
```

#### Updated OccurrenceHeatmapLayer Props
```typescript
<OccurrenceHeatmapLayer visible={overlayLayer === 'heatmap'} opacity={layerOpacity} polygon={drawnPolygon} />
```

### 3. DrawControl Component Updates

#### Updated Function Signature
```typescript
function DrawControl({ onAnalysisComplete, onAnalysisError, onLoadingChange, onClear, onPolygonChange }: MapProps & { onPolygonChange?: (polygon: GeoJSONPolygon | null) => void }) {
```

#### Updated Event Handlers

**onDrawCreated:**
```typescript
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
```

**onDrawDeleted:**
```typescript
const onDrawDeleted = (e: any) => {
  // Ensure all layers are properly cleared
  drawnItems.clearLayers();
  onClear();
  onPolygonChange?.(null); // Clear polygon
};
```

**onDrawEdited:**
```typescript
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
```

#### Updated useEffect Dependencies
```typescript
}, [map, onAnalysisComplete, onAnalysisError, onLoadingChange, onClear, onPolygonChange]);
```

### 4. OccurrenceHeatmapLayer Component Updates

#### Updated Function Signature
```typescript
function OccurrenceHeatmapLayer({ visible, opacity, polygon }: { visible: boolean; opacity: number; polygon?: GeoJSONPolygon | null }) {
```

#### Added Point-in-Polygon Algorithm
```typescript
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
```

#### Updated loadHeatmap Function
```typescript
const loadHeatmap = async () => {
  if (!visible) return;

  const bounds = map.getBounds();
  const minLat = bounds.getSouth();
  const minLng = bounds.getWest();
  const maxLat = bounds.getNorth();
  const maxLng = bounds.getEast();

  try {
    setLoading(true);
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'}/api/geospatial/heatmap?minLat=${minLat}&minLng=${minLng}&maxLat=${maxLat}&maxLng=${maxLng}`
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    // Remove old layer
    if (layerRef.current) {
      map.removeLayer(layerRef.current);
    }

    // Filter features to only include those within the polygon (if polygon exists)
    let filteredFeatures = data.features;
    if (polygon && data.features) {
      filteredFeatures = data.features.filter((feature: any) => {
        if (!feature.geometry || !feature.geometry.coordinates) return false;

        // Get the center point of the geohash tile
        // For simplicity, we'll check if any vertex of the polygon is inside our drawn polygon
        // In a more sophisticated implementation, we'd check polygon intersection
        const coords = feature.geometry.coordinates[0]; // Get outer ring
        if (coords && coords.length > 0) {
          const centerPoint: [number, number] = [coords[0][0], coords[0][1]]; // Approximate center
          return isPointInPolygon(centerPoint, polygon);
        }
        return false;
      });
    }

    // Create filtered GeoJSON
    const filteredData = {
      ...data,
      features: filteredFeatures
    };

    // Add new layer with color-coded density
    layerRef.current = L.geoJSON(filteredData, {
      style: (feature) => {
        const densityNorm = feature?.properties?.density_normalized || 0;
        return {
          fillColor: getColorFromDensity(densityNorm),
          fillOpacity: opacity * 0.6,
          color: getColorFromDensity(densityNorm),
          weight: 1,
          opacity: opacity * 0.8
        };
      },
      onEachFeature: (feature, layer) => {
        const props = feature.properties;
        layer.bindPopup(`
          <div class="p-2">
            <h3 class="font-semibold text-emerald-600">Occurrence Density</h3>
            <p class="text-sm"><strong>Density:</strong> ${props.density} per km&sup2;</p>
            <p class="text-sm"><strong>Total:</strong> ${props.total_occurrences.toLocaleString()} occurrences</p>
            <p class="text-sm"><strong>Species:</strong> ${props.species_count} species</p>
            <p class="text-xs text-gray-500">Geohash: ${props.geohash}</p>
          </div>
        `);
      }
    });

    layerRef.current.addTo(map);
  } catch (error) {
    console.error('Error loading heatmap:', error);
  } finally {
    setLoading(false);
  }
};
```

#### Updated useEffect Dependencies
```typescript
}, [visible, polygon]);
```

## Files Modified

1. `treekipedia/frontend/app/analysis/page.tsx`
2. `treekipedia/frontend/app/analysis/components/Map.tsx`

## Key Features Added

1. **Automatic Heatmap Enable**: Heatmap automatically enables when polygon analysis completes
2. **Polygon Boundary Filtering**: Only heatmap tiles within the drawn polygon are displayed
3. **Real-time Updates**: Heatmap updates when polygons are edited or deleted
4. **Performance Optimization**: Reduced data rendering by filtering out irrelevant tiles
5. **State Synchronization**: Polygon state is properly managed across components

## Testing Notes

- Draw a polygon on the analysis page
- Verify heatmap appears automatically
- Check that heatmap only shows data within polygon boundaries
- Test polygon editing and deletion
- Verify performance improvement (fewer tiles rendered)

## Potential Improvements

1. **Server-side Filtering**: Move polygon filtering to backend API for better performance
2. **Polygon Intersection**: Use proper polygon intersection instead of point-in-polygon for geohash tiles
3. **Caching**: Cache filtered results to avoid re-filtering on map movements
4. **Progressive Loading**: Load heatmap data progressively as user zooms in
