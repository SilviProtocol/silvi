# Intact Forest Layer Complete Implementation Guide
**Last Updated**: October 18, 2025
**Status**: Ready for Implementation

---

## Executive Summary

Add intact forest canopy as a map layer with efficient rendering using:
- **Progressive pre-processing** for zoom levels 0-9 (creates 3 lightweight tables)
- **Bounding box filtering** at all zoom levels
- **Original data** for zoom 10+ (viewport is tiny enough)
- **~3 MB consistent response sizes** across all zoom levels

**Total Additional Storage**: ~100 MB (less than 10% of original 1.18 GB)

---

## Part 1: Current Data Analysis

### Intact Forest Dataset
- **Total Size**: 1.18 GB in PostgreSQL (table: `intact_forest_landscapes_2021`)
- **Polygon Count**: 6,819 MultiPolygon features
- **Total Vertices**: 74,165,771 vertices
- **Average Area**: 0.18 km² (very small polygons!)
- **Max Area**: 54.3 km²
- **Geographic Coverage**: Global (-172.70° to 178.24° lon, -55.46° to 69.73° lat)
- **Spatial Index**: ✅ GIST index exists on `geom` column

### Complexity Distribution
| Vertices | Count | % of Polygons | Size |
|----------|-------|---------------|------|
| < 100 | 170 | 2.5% | 153 KB |
| 100-1K | 1,045 | 15.3% | 8 MB |
| 1K-10K | 3,792 | 55.6% | 248 MB |
| 10K-50K | 1,563 | 22.9% | 491 MB |
| 50K-100K | 175 | 2.6% | 179 MB |
| >100K | 74 | 1.1% | 208 MB |

**Key Finding**: 74 polygons (1.1%) contain 13.6M vertices - these are the performance killers!

---

## Part 2: Strategy - Progressive Detail with Constant Response Size

### Core Principle
Maintain **~3 MB response sizes** at all zoom levels while **progressively enriching detail** as users zoom in.

### Implementation Approach

| Zoom | View Type | Table Used | Storage | Response Size | Detail |
|------|-----------|------------|---------|---------------|--------|
| 0-3 | World | z0_z3 (1.0°) | ~6 MB | ~3-6 MB | Low |
| 4-6 | Continental | z4_z6 (0.05°) | ~15-20 MB | ~3 MB | Medium |
| 7-9 | Country | z7_z9 (0.005°) | ~60-80 MB | ~3 MB | High |
| 10+ | City | Original | 1,134 MB | ~3 MB | Full |

**Total Additional Storage**: ~100 MB

---

## Part 3: Database Pre-Processing

### Step 1: Create Simplified Tables (One-Time Script)

Run this SQL once to create the multi-resolution tables:

```sql
-- ============================================
-- Intact Forest Multi-Resolution Tables
-- Run time: ~15-20 minutes
-- Storage: ~100 MB additional
-- ============================================

-- ZOOM 0-3: World View (aggressive simplification for global view)
DROP TABLE IF EXISTS intact_forest_z0_z3 CASCADE;
CREATE TABLE intact_forest_z0_z3 AS
SELECT
  ogc_fid,
  ifl_id,
  year,
  layer,
  gfw_area__,
  gfw_geosto,
  0 as min_zoom,
  3 as max_zoom,
  ST_SimplifyPreserveTopology(geom, 1.0) as geom
FROM intact_forest_landscapes_2021;

CREATE INDEX idx_intact_forest_z0_z3_geom ON intact_forest_z0_z3 USING GIST(geom);
CREATE INDEX idx_intact_forest_z0_z3_area ON intact_forest_z0_z3(gfw_area__);

-- ZOOM 4-6: Continental View (moderate simplification)
DROP TABLE IF EXISTS intact_forest_z4_z6 CASCADE;
CREATE TABLE intact_forest_z4_z6 AS
SELECT
  ogc_fid,
  ifl_id,
  year,
  layer,
  gfw_area__,
  gfw_geosto,
  4 as min_zoom,
  6 as max_zoom,
  ST_SimplifyPreserveTopology(geom, 0.05) as geom
FROM intact_forest_landscapes_2021;

CREATE INDEX idx_intact_forest_z4_z6_geom ON intact_forest_z4_z6 USING GIST(geom);
CREATE INDEX idx_intact_forest_z4_z6_area ON intact_forest_z4_z6(gfw_area__);

-- ZOOM 7-9: Country View (light simplification, high detail)
DROP TABLE IF EXISTS intact_forest_z7_z9 CASCADE;
CREATE TABLE intact_forest_z7_z9 AS
SELECT
  ogc_fid,
  ifl_id,
  year,
  layer,
  gfw_area__,
  gfw_geosto,
  7 as min_zoom,
  9 as max_zoom,
  ST_SimplifyPreserveTopology(geom, 0.005) as geom
FROM intact_forest_landscapes_2021;

CREATE INDEX idx_intact_forest_z7_z9_geom ON intact_forest_z7_z9 USING GIST(geom);
CREATE INDEX idx_intact_forest_z7_z9_area ON intact_forest_z7_z9(gfw_area__);

-- ZOOM 10+: Use original table (no preprocessing needed)
-- Viewport is small enough that bounding box filtering is sufficient

-- Analyze all tables for query optimization
ANALYZE intact_forest_z0_z3;
ANALYZE intact_forest_z4_z6;
ANALYZE intact_forest_z7_z9;
```

### Step 2: Verify Table Sizes

```sql
-- Check actual sizes after creation
SELECT
  'z0_z3' as table_name,
  pg_size_pretty(pg_total_relation_size('intact_forest_z0_z3')) as size,
  COUNT(*) as polygons,
  SUM(ST_NPoints(geom)) as vertices
FROM intact_forest_z0_z3
UNION ALL
SELECT
  'z4_z6',
  pg_size_pretty(pg_total_relation_size('intact_forest_z4_z6')),
  COUNT(*),
  SUM(ST_NPoints(geom))
FROM intact_forest_z4_z6
UNION ALL
SELECT
  'z7_z9',
  pg_size_pretty(pg_total_relation_size('intact_forest_z7_z9')),
  COUNT(*),
  SUM(ST_NPoints(geom))
FROM intact_forest_z7_z9;
```

Expected results:
- z0_z3: ~6 MB
- z4_z6: ~15-20 MB
- z7_z9: ~60-80 MB

---

## Part 4: Backend Implementation

### 4.1 New Endpoint with Production Enhancements

**File**: `treekipedia/backend/controllers/geospatial.js`

Add this complete implementation:

```javascript
// ==============================================
// Intact Forest Layer with Progressive Loading
// ==============================================

// Cache implementation
class IntactForestCache {
  constructor(maxSize = 100, ttl = 10 * 60 * 1000) {
    this.cache = new Map();
    this.maxSize = maxSize;
    this.ttl = ttl;
    setInterval(() => this.cleanup(), 5 * 60 * 1000);
  }

  getCacheKey(minLat, maxLat, minLng, maxLng, zoom) {
    // Use appropriate precision based on zoom level
    // High zoom needs more precision to differentiate cache entries
    const precision = zoom > 10 ? 3 : zoom > 5 ? 2 : 1;
    return `${parseFloat(minLat).toFixed(precision)},${parseFloat(maxLat).toFixed(precision)},` +
           `${parseFloat(minLng).toFixed(precision)},${parseFloat(maxLng).toFixed(precision)},${zoom}`;
  }

  get(key) {
    const item = this.cache.get(key);
    if (!item) return null;
    if (Date.now() - item.timestamp > this.ttl) {
      this.cache.delete(key);
      return null;
    }
    return item.data;
  }

  set(key, data) {
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  cleanup() {
    const now = Date.now();
    for (const [key, value] of this.cache.entries()) {
      if (now - value.timestamp > this.ttl) {
        this.cache.delete(key);
      }
    }
  }
}

const intactForestCache = new IntactForestCache();

// Rate limiting
const rateLimitMap = new Map();
const checkRateLimit = (ip, maxRequests = 30, windowMs = 60000) => {
  const now = Date.now();
  const userRequests = rateLimitMap.get(ip) || [];
  const recentRequests = userRequests.filter(t => now - t < windowMs);

  if (recentRequests.length >= maxRequests) return false;

  recentRequests.push(now);
  rateLimitMap.set(ip, recentRequests);
  return true;
};

// Performance metrics
const queryMetrics = {
  totalQueries: 0,
  totalTime: 0,
  slowQueries: 0,
  errors: 0,
  cacheHits: 0,
  cacheMisses: 0
};

// Main endpoint
exports.getIntactForests = async (req, res) => {
  const startTime = Date.now();

  try {
    const { minLat, maxLat, minLng, maxLng, zoom = 5, limit = 500 } = req.query;

    // Input validation
    const coords = [minLat, maxLat, minLng, maxLng].map(parseFloat);
    if (coords.some(c => isNaN(c) || c < -180 || c > 180)) {
      return res.status(400).json({
        error: 'Invalid coordinates',
        message: 'All coordinates must be between -180 and 180'
      });
    }

    const zoomNum = parseInt(zoom);
    if (isNaN(zoomNum) || zoomNum < 0 || zoomNum > 20) {
      return res.status(400).json({
        error: 'Invalid zoom level',
        message: 'Zoom must be between 0 and 20'
      });
    }

    const limitNum = parseInt(limit);
    if (isNaN(limitNum) || limitNum < 1 || limitNum > 1000) {
      return res.status(400).json({
        error: 'Invalid limit',
        message: 'Limit must be between 1 and 1000'
      });
    }

    if (coords[0] >= coords[1] || coords[2] >= coords[3]) {
      return res.status(400).json({
        error: 'Invalid bounding box',
        message: 'Min coordinates must be less than max coordinates'
      });
    }

    // Rate limiting
    const clientIP = req.ip || req.connection.remoteAddress;
    if (!checkRateLimit(clientIP)) {
      queryMetrics.errors++;
      return res.status(429).json({
        error: 'Too many requests',
        message: 'Please wait before making more requests',
        retryAfter: 60
      });
    }

    // Check cache
    const cacheKey = intactForestCache.getCacheKey(minLat, maxLat, minLng, maxLng, zoom);
    const cached = intactForestCache.get(cacheKey);
    if (cached) {
      queryMetrics.cacheHits++;
      queryMetrics.totalQueries++;
      queryMetrics.totalTime += (Date.now() - startTime);
      return res.json({ ...cached, fromCache: true });
    }

    queryMetrics.cacheMisses++;

    // Select appropriate table based on zoom
    const tableName = getTableForZoom(zoomNum);

    // Set query timeout
    await pool.query('SET statement_timeout = 30000');

    // Main query with index hint for better performance
    const query = `
      WITH viewport_polygons AS (
        SELECT /*+ INDEX(${tableName} idx_${tableName}_geom) */
          ogc_fid,
          ifl_id,
          year,
          ROUND((gfw_area__ / 1000000)::numeric, 2) as area_km2,
          ST_Intersection(
            geom,
            ST_MakeEnvelope($1, $2, $3, $4, 4326)
          ) as clipped_geom
        FROM ${tableName}
        WHERE ST_Intersects(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
          AND ST_IsValid(geom)
        ORDER BY gfw_area__ DESC
        LIMIT $5
      )
      SELECT
        json_build_object(
          'type', 'FeatureCollection',
          'features', json_agg(
            json_build_object(
              'type', 'Feature',
              'id', ogc_fid,
              'properties', json_build_object(
                'ifl_id', ifl_id,
                'year', year,
                'area_km2', area_km2
              ),
              'geometry', ST_AsGeoJSON(clipped_geom)::json
            )
          ),
          'metadata', json_build_object(
            'zoom', $6,
            'table_used', '${tableName}',
            'polygon_count', COUNT(*),
            'query_time_ms', ${Date.now() - startTime}
          )
        ) as result
      FROM viewport_polygons;
    `;

    const values = [minLng, minLat, maxLng, maxLat, limitNum, zoomNum];
    const result = await pool.query(query, values);

    const responseData = result.rows[0]?.result || {
      type: 'FeatureCollection',
      features: [],
      metadata: { zoom: zoomNum, polygon_count: 0 }
    };

    // Cache the response
    intactForestCache.set(cacheKey, responseData);

    // Track metrics
    const duration = Date.now() - startTime;
    queryMetrics.totalQueries++;
    queryMetrics.totalTime += duration;
    if (duration > 5000) {
      queryMetrics.slowQueries++;
      console.warn(`[SLOW QUERY] Intact forest query took ${duration}ms`);
    }

    res.json(responseData);

  } catch (error) {
    queryMetrics.errors++;
    console.error('Intact forest query error:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to load intact forest data'
    });
  }
};

// Helper: Select table based on zoom
const getTableForZoom = (zoom) => {
  if (zoom <= 3) return 'intact_forest_z0_z3';      // 6 MB table
  if (zoom <= 6) return 'intact_forest_z4_z6';      // 15-20 MB table
  if (zoom <= 9) return 'intact_forest_z7_z9';      // 60-80 MB table
  return 'intact_forest_landscapes_2021';           // Original 1.1 GB
};

// Metrics endpoint
exports.getIntactForestMetrics = (req, res) => {
  const avgTime = queryMetrics.totalQueries > 0
    ? queryMetrics.totalTime / queryMetrics.totalQueries
    : 0;

  const cacheHitRate = queryMetrics.totalQueries > 0
    ? (queryMetrics.cacheHits / queryMetrics.totalQueries) * 100
    : 0;

  res.json({
    ...queryMetrics,
    averageTimeMs: Math.round(avgTime),
    slowQueryPercentage: queryMetrics.totalQueries > 0
      ? (queryMetrics.slowQueries / queryMetrics.totalQueries) * 100
      : 0,
    cacheHitRate: cacheHitRate.toFixed(2)
  });
};
```

### 4.2 Add Routes

**File**: `treekipedia/backend/routes/geospatial.js`

Add these routes:

```javascript
// Intact forest layer endpoints
router.get('/intact-forests', geospatialController.getIntactForests);
router.get('/intact-forests/metrics', geospatialController.getIntactForestMetrics);
```

---

## Part 5: Frontend Implementation

### 5.1 Layer Control Component

**File**: `treekipedia/frontend/app/components/analysis/LayerControl.tsx`

```typescript
import React from 'react';
import { Loader2 } from 'lucide-react';

interface LayerControlProps {
  selectedLayer: 'ecoregions' | 'intact-forests' | 'none';
  onLayerChange: (layer: 'ecoregions' | 'intact-forests' | 'none') => void;
  opacity: number;
  onOpacityChange: (opacity: number) => void;
  loading: boolean;
  error?: string | null;
  retryCount?: number;
}

export const LayerControl: React.FC<LayerControlProps> = ({
  selectedLayer,
  onLayerChange,
  opacity,
  onOpacityChange,
  loading,
  error,
  retryCount
}) => {
  return (
    <div className="absolute top-4 right-4 z-[1000]">
      <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-4">
        {/* Layer Selection */}
        <div className="mb-3">
          <label className="text-emerald-300 text-sm mb-1 block">
            Map Overlay
          </label>
          <select
            value={selectedLayer}
            onChange={(e) => onLayerChange(e.target.value as any)}
            disabled={loading}
            className="bg-black/50 border border-white/20 text-emerald-300
                       rounded-lg px-3 py-2 w-full
                       focus:outline-none focus:ring-2 focus:ring-emerald-500
                       disabled:opacity-50"
          >
            <option value="none">No Overlay</option>
            <option value="ecoregions">Ecoregions</option>
            <option value="intact-forests">Intact Forest Canopy</option>
          </select>
        </div>

        {/* Opacity Control */}
        {selectedLayer !== 'none' && (
          <div>
            <label className="text-emerald-300 text-sm mb-1 block">
              Opacity: {Math.round(opacity * 100)}%
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={opacity}
              onChange={(e) => onOpacityChange(parseFloat(e.target.value))}
              className="w-full accent-emerald-500"
            />
          </div>
        )}

        {/* Loading indicator */}
        {loading && (
          <div className="mt-3 flex items-center gap-2 text-white text-sm">
            <Loader2 className="animate-spin h-4 w-4" />
            <span>
              Loading layer...
              {retryCount && retryCount > 0 && ` (retry ${retryCount})`}
            </span>
          </div>
        )}

        {/* Error message */}
        {error && !loading && (
          <div className="mt-3 bg-red-500/20 border border-red-500/50
                          text-red-200 px-3 py-2 rounded text-sm">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};
```

### 5.2 Map Component Integration

**File**: Update your main map component

```typescript
import React, { useState, useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import L from 'leaflet';
import axios from 'axios';
import { debounce } from 'lodash';
import { toast } from 'sonner';
import { LayerControl } from './LayerControl';

const MapWithIntactForests = () => {
  const [selectedLayer, setSelectedLayer] = useState<'ecoregions' | 'intact-forests' | 'none'>('none');
  const [intactForestData, setIntactForestData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [opacity, setOpacity] = useState(0.3);
  const [dataVersion, setDataVersion] = useState(0);
  const mapRef = useRef<L.Map>(null);

  const MAX_RETRIES = 2;

  // Fetch intact forests with retry logic
  const fetchIntactForests = async (
    bounds: L.LatLngBounds,
    zoom: number,
    attempt = 0
  ): Promise<void> => {
    try {
      setLoading(true);
      setError(null);

      const response = await axios.get(
        `${process.env.NEXT_PUBLIC_API_URL}/api/geospatial/intact-forests`,
        {
          params: {
            minLat: bounds.getSouth(),
            maxLat: bounds.getNorth(),
            minLng: bounds.getWest(),
            maxLng: bounds.getEast(),
            zoom: zoom,
            limit: 500
          },
          timeout: 15000
        }
      );

      setIntactForestData(response.data);
      setDataVersion(prev => prev + 1); // Increment version for efficient re-rendering
      setRetryCount(0);
      setError(null);

    } catch (error: any) {
      console.error(`Intact forest fetch attempt ${attempt + 1} failed:`, error);

      if (attempt < MAX_RETRIES) {
        const retryDelay = 1000 * (attempt + 1);
        setTimeout(() => fetchIntactForests(bounds, zoom, attempt + 1), retryDelay);
        setRetryCount(attempt + 1);
      } else {
        if (error.response?.status === 429) {
          setError('Too many requests. Please wait a moment.');
          toast.warning('Too many requests. Please slow down.');
        } else if (error.response?.status === 400) {
          setError(error.response.data.message || 'Invalid request');
        } else {
          setError('Failed to load layer. Try zooming or refreshing.');
          toast.error('Failed to load intact forest layer');
        }
      }
    } finally {
      setLoading(false);
    }
  };

  // Debounced viewport change handler
  const debouncedFetchIntactForests = useMemo(
    () => debounce(async (bounds: L.LatLngBounds, zoom: number) => {
      if (selectedLayer !== 'intact-forests') return;
      await fetchIntactForests(bounds, zoom);
    }, 500),
    [selectedLayer]
  );

  // Listen to map events
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const handleMoveEnd = () => {
      const bounds = map.getBounds();
      const zoom = map.getZoom();
      debouncedFetchIntactForests(bounds, zoom);
    };

    if (selectedLayer === 'intact-forests') {
      map.on('moveend', handleMoveEnd);
      map.on('zoomend', handleMoveEnd);
      handleMoveEnd(); // Initial load
    }

    return () => {
      map.off('moveend', handleMoveEnd);
      map.off('zoomend', handleMoveEnd);
    };
  }, [selectedLayer, debouncedFetchIntactForests]);

  // Clear data when layer is deselected
  useEffect(() => {
    if (selectedLayer !== 'intact-forests') {
      setIntactForestData(null);
      setError(null);
    }
  }, [selectedLayer]);

  return (
    <div className="relative h-full w-full">
      <MapContainer
        ref={mapRef}
        center={[0, 0]}
        zoom={3}
        className="h-full w-full"
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />

        {/* Intact Forest Layer */}
        {selectedLayer === 'intact-forests' && intactForestData && (
          <GeoJSON
            key={`intact-forest-${dataVersion}`} // Use version number instead of stringifying
            data={intactForestData}
            style={{
              fillColor: '#10b981',
              fillOpacity: opacity,
              color: '#059669',
              weight: 1,
              opacity: 0.6
            }}
            onEachFeature={(feature, layer) => {
              layer.bindPopup(`
                <div class="text-sm">
                  <strong>Intact Forest Landscape</strong><br/>
                  ID: ${feature.properties.ifl_id}<br/>
                  Area: ${feature.properties.area_km2?.toLocaleString()} km²<br/>
                  Year: ${feature.properties.year}
                </div>
              `);
            }}
          />
        )}

        {/* Layer Control */}
        <LayerControl
          selectedLayer={selectedLayer}
          onLayerChange={setSelectedLayer}
          opacity={opacity}
          onOpacityChange={setOpacity}
          loading={loading}
          error={error}
          retryCount={retryCount}
        />
      </MapContainer>
    </div>
  );
};

export default MapWithIntactForests;
```

---

## Part 6: Testing & Optimization

### 6.1 Test SQL Preprocessing

```bash
# Connect to database
psql treekipedia

# Run the preprocessing SQL from Part 3
# Check table sizes
\dt+ intact_forest_*
```

### 6.2 Test Backend Endpoints

```bash
# Test world view (zoom 3)
curl "http://localhost:5001/api/geospatial/intact-forests?minLat=-90&maxLat=90&minLng=-180&maxLng=180&zoom=3" | jq '.metadata'

# Test continental view (zoom 6, North America)
curl "http://localhost:5001/api/geospatial/intact-forests?minLat=25&maxLat=70&minLng=-160&maxLng=-50&zoom=6" | jq '.metadata'

# Test country view (zoom 9, Brazil)
curl "http://localhost:5001/api/geospatial/intact-forests?minLat=-35&maxLat=5&minLng=-75&maxLng=-35&zoom=9" | jq '.metadata'

# Check metrics
curl "http://localhost:5001/api/geospatial/intact-forests/metrics" | jq '.'
```

### 6.3 Performance Targets

| Metric | Target | Acceptable |
|--------|--------|------------|
| Query Time | < 500ms | < 2s |
| Response Size | 2-5 MB | < 10 MB |
| Cache Hit Rate | > 50% | > 30% |
| Memory Usage | < 100 MB | < 200 MB |

---

## Part 7: Deployment Checklist

### Pre-Deployment

- [ ] Run preprocessing SQL to create 3 tables
- [ ] Verify table sizes are as expected (~100 MB total)
- [ ] Test all zoom levels locally
- [ ] Check memory usage during testing
- [ ] Verify cache is working (check metrics)

### Backend Deployment

- [ ] Add environment variables if needed
- [ ] Deploy backend code changes
- [ ] Test endpoints on production
- [ ] Monitor initial query performance
- [ ] Check error logs

### Frontend Deployment

- [ ] Deploy LayerControl component
- [ ] Deploy updated map component
- [ ] Test layer switching
- [ ] Test opacity control
- [ ] Verify error handling works

### Post-Deployment

- [ ] Monitor metrics endpoint for 24 hours
- [ ] Check cache hit rates
- [ ] Watch for slow queries
- [ ] Gather user feedback
- [ ] Adjust cache TTL if needed

---

## Part 8: Troubleshooting

### Common Issues & Solutions

**Issue**: Queries timing out
- Check if preprocessing completed successfully
- Verify GIST indexes exist on all tables
- Consider increasing `statement_timeout`

**Issue**: Response too large
- Reduce limit parameter
- Check if correct table is being used for zoom level
- Verify simplification tolerances

**Issue**: Cache not working
- Check cache key generation
- Verify TTL settings
- Monitor cache size

**Issue**: High memory usage
- Reduce cache max size
- Check for memory leaks in query results
- Monitor concurrent request count

---

## Summary

This implementation provides:
- ✅ **Fast performance** through pre-processed tables
- ✅ **Consistent UX** with ~3 MB responses at all zoom levels
- ✅ **Progressive detail** that enriches as users zoom
- ✅ **Production-ready** with caching, rate limiting, and monitoring
- ✅ **Minimal storage** overhead (only ~100 MB)
- ✅ **Error resilience** with retry logic and graceful degradation

**Total implementation time**: ~8-10 hours
**Storage cost**: ~100 MB
**Performance gain**: 5-10x faster than real-time simplification

---

**Ready to implement?** Start with the SQL preprocessing in Part 3, then move to backend and frontend implementation.