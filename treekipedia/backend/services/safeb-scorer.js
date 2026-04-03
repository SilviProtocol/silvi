/**
 * SAFE-B Species Recommendation Scoring Engine
 * =============================================
 * Implements the 5-component scoring framework for species recommendations:
 *
 *   S - Spatial:    Occurrence density and range proximity
 *   A - Abiotic:    Climate, soil, elevation match
 *   F - Functional: Trait suitability for restoration goals
 *   E - Ecosystem:  Ecoregion, biome, GET match
 *   B - Biotic:     Interaction network viability (GloBI)
 *
 * Each component returns a score 0-1. Components are weighted by restoration strategy.
 *
 * Usage:
 *   const scorer = new SafeBScorer(pool);
 *   const scored = await scorer.scoreSpecies(candidates, locationContext, strategy);
 */

const { Pool } = require('pg');

// ===========================================================================
// Strategy Weight Presets
// ===========================================================================

const STRATEGY_WEIGHTS = {
    general: {
        spatial: 0.20, abiotic: 0.25, functional: 0.20, ecosystem: 0.20, biotic: 0.15,
        description: 'Balanced scoring for general restoration'
    },
    rewilding: {
        spatial: 0.20, abiotic: 0.15, functional: 0.10, ecosystem: 0.30, biotic: 0.25,
        description: 'Native species restoration, ecological integrity'
    },
    agroforestry: {
        spatial: 0.10, abiotic: 0.25, functional: 0.40, ecosystem: 0.15, biotic: 0.10,
        description: 'Productive tree systems for food, timber, income'
    },
    riparian: {
        spatial: 0.15, abiotic: 0.35, functional: 0.20, ecosystem: 0.20, biotic: 0.10,
        description: 'Waterway restoration, bank stabilization, water quality'
    },
    carbon: {
        spatial: 0.10, abiotic: 0.20, functional: 0.50, ecosystem: 0.15, biotic: 0.05,
        description: 'Maximum carbon sequestration and storage'
    },
    biodiversity: {
        spatial: 0.15, abiotic: 0.15, functional: 0.20, ecosystem: 0.25, biotic: 0.25,
        description: 'Maximum species diversity and ecological interactions'
    },
    erosion_control: {
        spatial: 0.15, abiotic: 0.30, functional: 0.30, ecosystem: 0.15, biotic: 0.10,
        description: 'Soil stabilization and erosion prevention'
    }
};

// ===========================================================================
// Functional Trait Priorities by Strategy
// ===========================================================================

const FUNCTIONAL_PRIORITIES = {
    general: {
        native_bonus: 0.3,
        traits: {} // No trait bonuses
    },
    rewilding: {
        native_bonus: 0.5,
        traits: {
            late_successional: 0.3, // successional_stage contains 'late' or 'climax'
            shade_tolerant: 0.2,    // tolerances contains 'shade'
            wildlife_support: 0.3,  // has GloBI pollinators/dispersers
            structural_diversity: 0.2 // canopy or emergent layer
        }
    },
    agroforestry: {
        native_bonus: 0.1,
        traits: {
            fast_growth: 0.2,       // growth form = tree, lifespan suggests fast
            multi_use: 0.3,         // agroforestry_use_cases or non_timber_products
            nitrogen_fixing: 0.2,   // tolerances/traits mention nitrogen
            food_production: 0.3    // agroforestry_use_cases mentions food/fruit
        }
    },
    riparian: {
        native_bonus: 0.3,
        traits: {
            flood_tolerance: 0.35,  // tolerances mentions flood/waterlog
            bank_stabilization: 0.25, // root characteristics
            water_tolerance: 0.2,   // tolerances mentions wet
            native: 0.2
        }
    },
    carbon: {
        native_bonus: 0.15,
        traits: {
            tall_tree: 0.3,         // maximum_height > 20m
            long_lived: 0.25,       // lifespan suggests long
            fast_biomass: 0.25,     // growth form = tree, fast growing
            timber_quality: 0.2     // timber_value is not NA
        }
    },
    biodiversity: {
        native_bonus: 0.4,
        traits: {
            interaction_richness: 0.3, // Many GloBI interactions
            structural_diversity: 0.2, // Different forest layers
            keystone_potential: 0.2,   // Many species depend on it
            native: 0.3
        }
    },
    erosion_control: {
        native_bonus: 0.2,
        traits: {
            root_system: 0.3,       // Deep/extensive roots
            fast_establishing: 0.3, // Pioneer or early successional
            ground_cover: 0.2,      // Understory/ground layer
            drought_tolerance: 0.2  // tolerances mentions drought
        }
    }
};


class SafeBScorer {
    constructor(pool) {
        this.pool = pool;
    }

    /**
     * Score a list of candidate species using the full SAFE-B framework.
     *
     * @param {Array} candidates - Species with at least taxon_id and similarity from pgvector
     * @param {Object} locationContext - { lat, lon, elevation, ecoregion, biome, realm, countries, wcvpPatterns }
     * @param {string} strategy - Restoration strategy key (from STRATEGY_WEIGHTS)
     * @param {Object} options - { includeIntroduced, minSimilarity }
     * @returns {Array} Scored and ranked species
     */
    async scoreSpecies(candidates, locationContext, strategy = 'general', options = {}) {
        const weights = STRATEGY_WEIGHTS[strategy] || STRATEGY_WEIGHTS.general;
        const funcPriorities = FUNCTIONAL_PRIORITIES[strategy] || FUNCTIONAL_PRIORITIES.general;
        const { includeIntroduced = false } = options;

        // Get spatial scores and tile counts for all candidate species in batch
        const taxonIds = candidates.map(c => c.taxon_id);
        const { scores: spatialScores, tileCounts: spatialTileCounts } = await this.batchSpatialScore(taxonIds, locationContext.lat, locationContext.lon);

        const scored = candidates.map(candidate => {
            // Component S: Spatial
            const spatialScore = spatialScores[candidate.taxon_id] || 0;

            // Component A: Abiotic
            const abioticScore = this.computeAbioticScore(candidate, locationContext);

            // Component F: Functional
            const functionalScore = this.computeFunctionalScore(candidate, strategy, funcPriorities);

            // Component E: Ecosystem (with spatial tile count for partial ecoregion credit)
            const spatialTileCount = spatialTileCounts[candidate.taxon_id] || 0;
            const ecosystemScore = this.computeEcosystemScore(candidate, locationContext, spatialTileCount);

            // Component B: Biotic
            const bioticScore = this.computeBioticScore(candidate);

            // Weighted total
            const safebTotal =
                weights.spatial * spatialScore +
                weights.abiotic * abioticScore +
                weights.functional * functionalScore +
                weights.ecosystem * ecosystemScore +
                weights.biotic * bioticScore;

            // Native status assessment
            const nativeStatus = this.assessNativeStatus(candidate, locationContext);

            // Apply hard filters
            let filtered = false;
            let filterReason = null;

            // Exclude invasive species from recommendations (always)
            if (nativeStatus.isInvasive) {
                filtered = true;
                filterReason = 'Invasive species excluded from recommendations';
            }

            // For rewilding/biodiversity, exclude introduced species
            if (!includeIntroduced && (strategy === 'rewilding' || strategy === 'biodiversity')) {
                if (nativeStatus.status === 'introduced' && !nativeStatus.isNative) {
                    filtered = true;
                    filterReason = `Introduced species excluded for ${strategy} strategy`;
                }
            }

            // Native bonus (applied as multiplier, not added score)
            let nativeMultiplier = 1.0;
            if (nativeStatus.isNative) {
                nativeMultiplier = 1.0 + funcPriorities.native_bonus;
            } else if (nativeStatus.status === 'introduced') {
                nativeMultiplier = 0.85; // Slight penalty for introduced
            }

            const finalScore = Math.min(1.0, safebTotal * nativeMultiplier);

            // Confidence based on data availability
            const dataPoints = [
                spatialScore > 0 ? 1 : 0,
                abioticScore > 0 ? 1 : 0,
                functionalScore > 0 ? 1 : 0,
                ecosystemScore > 0 ? 1 : 0,
                bioticScore > 0 ? 1 : 0
            ];
            const confidence = dataPoints.reduce((a, b) => a + b, 0) / 5;

            return {
                taxon_id: candidate.taxon_id,
                scientific_name: candidate.accepted_scientific_name || candidate.scientific_name,
                common_name: candidate.common_name,
                family: candidate.family,

                // SAFE-B scores
                safeb_score: Math.round(finalScore * 100),
                safeb_components: {
                    spatial: Math.round(spatialScore * 100),
                    abiotic: Math.round(abioticScore * 100),
                    functional: Math.round(functionalScore * 100),
                    ecosystem: Math.round(ecosystemScore * 100),
                    biotic: Math.round(bioticScore * 100)
                },
                habitat_similarity: candidate.similarity ? parseFloat(candidate.similarity) : null,

                // Strategy context
                strategy,
                weights: {
                    spatial: weights.spatial,
                    abiotic: weights.abiotic,
                    functional: weights.functional,
                    ecosystem: weights.ecosystem,
                    biotic: weights.biotic
                },

                // Native status
                native_status: nativeStatus.status,
                is_native: nativeStatus.isNative,
                is_introduced: nativeStatus.isIntroduced,
                is_invasive: nativeStatus.isInvasive,
                native_multiplier: nativeMultiplier,

                // Confidence
                confidence: Math.round(confidence * 100),

                // Filtering
                filtered,
                filter_reason: filterReason,

                // Original attributes
                attributes: {
                    growth_form: candidate.growth_form || candidate.growth_form_ai,
                    successional_stage: candidate.successional_stage,
                    ecoregions: candidate.ecoregions,
                    conservation_status: candidate.conservation_status || candidate.conservation_status_ai,
                    cluster_elevation: candidate.mean_elevation || candidate.cluster_elevation,
                    occurrence_count: candidate.occurrence_count
                }
            };
        });

        // Filter out excluded species and sort by score
        const included = scored.filter(s => !s.filtered);
        const excluded = scored.filter(s => s.filtered);

        included.sort((a, b) => b.safeb_score - a.safeb_score);
        included.forEach((s, i) => { s.rank = i + 1; });

        return { recommendations: included, excluded };
    }

    // ===========================================================================
    // Component S: Spatial Score
    // ===========================================================================

    /**
     * Batch spatial scoring using geohash_species_tiles.
     * Checks if species have occurrence records near the query location.
     */
    async batchSpatialScore(taxonIds, lat, lon) {
        const scores = {};
        const tileCounts = {};
        if (!taxonIds.length || !lat || !lon) return { scores, tileCounts };

        try {
            // Search within 50km radius for species occurrences
            const result = await this.pool.query(`
                WITH nearby_tiles AS (
                    SELECT
                        geohash_l7,
                        species_data,
                        ST_Distance(
                            geometry::geography,
                            ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                        ) as dist_m
                    FROM geohash_species_tiles
                    WHERE ST_DWithin(
                        geometry::geography,
                        ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                        50000
                    )
                )
                SELECT
                    key as taxon_id,
                    SUM(
                        CASE
                            WHEN jsonb_typeof(value) = 'number' THEN value::text::float
                            WHEN jsonb_typeof(value) = 'object' THEN COALESCE((value->>'count')::float, 1)
                            ELSE 1
                        END / GREATEST(dist_m, 150)
                    ) as proximity_score,
                    COUNT(*) as tile_count,
                    MIN(dist_m) as min_distance
                FROM nearby_tiles,
                     jsonb_each(species_data) as kv(key, value)
                WHERE key = ANY($3)
                GROUP BY key
            `, [lon, lat, taxonIds]);

            // Normalize scores to 0-1
            const maxScore = result.rows.length > 0
                ? Math.max(...result.rows.map(r => parseFloat(r.proximity_score)))
                : 1;

            for (const row of result.rows) {
                const raw = parseFloat(row.proximity_score) / Math.max(maxScore, 0.001);
                // Boost for very close occurrences
                const distBonus = row.min_distance < 5000 ? 0.2 : (row.min_distance < 20000 ? 0.1 : 0);
                scores[row.taxon_id] = Math.min(1.0, raw + distBonus);
                tileCounts[row.taxon_id] = parseInt(row.tile_count) || 0;
            }
        } catch (error) {
            console.error('Spatial scoring error:', error.message);
        }

        return { scores, tileCounts };
    }

    // ===========================================================================
    // Component A: Abiotic Score
    // ===========================================================================

    /**
     * Score climate, soil, and elevation match between location and species profile.
     * Uses species table columns for climate envelopes and soil preferences.
     */
    computeAbioticScore(species, locationContext) {
        const scores = [];

        // Elevation match (if both available)
        if (locationContext.elevation != null && species.mean_elevation != null) {
            const elevDiff = Math.abs(locationContext.elevation - species.mean_elevation);
            // Score decays with distance: 1.0 at 0m, 0.5 at 500m, 0.0 at 1500m
            const elevScore = Math.max(0, 1.0 - elevDiff / 1500);
            scores.push(elevScore);
        }

        // Climate match: precipitation range
        if (species.annual_precipitation_mm && species.annual_precipitation_mm !== 'NA') {
            const precipMatch = this.matchRange(
                species.annual_precipitation_mm,
                locationContext.precipitation
            );
            if (precipMatch !== null) scores.push(precipMatch);
        }

        // Climate match: temperature range
        if (species.annual_temperature_range_c && species.annual_temperature_range_c !== 'NA') {
            const tempMatch = this.matchRange(
                species.annual_temperature_range_c,
                locationContext.temperature
            );
            if (tempMatch !== null) scores.push(tempMatch);
        }

        // Soil pH match
        if (species.ph_prefered && species.ph_prefered !== 'NA' && locationContext.soil_ph) {
            const phMatch = this.matchSoilCategory(species.ph_prefered, locationContext.soil_ph);
            scores.push(phMatch);
        }

        // Soil texture match
        if (species.soil_texture_prefered && species.soil_texture_prefered !== 'NA' && locationContext.soil_texture) {
            const textureMatch = this.matchSoilCategory(species.soil_texture_prefered, locationContext.soil_texture);
            scores.push(textureMatch);
        }

        // Koppen-Geiger climate zone match
        if (locationContext.koppen_code && species.climate_type_koppengeiger && species.climate_type_koppengeiger !== 'NA') {
            const speciesKoppens = species.climate_type_koppengeiger.split(';').map(s => {
                const code = s.trim().split(' ')[0];
                return code;
            }).filter(Boolean);
            
            if (speciesKoppens.length > 0) {
                if (speciesKoppens.includes(locationContext.koppen_code)) {
                    scores.push(1.0); // Exact match
                } else {
                    const locationGroup = locationContext.koppen_code[0];
                    const hasGroupMatch = speciesKoppens.some(k => k[0] === locationGroup);
                    if (hasGroupMatch) {
                        scores.push(0.6); // Same major climate group
                    } else {
                        scores.push(0.2); // Different climate group
                    }
                }
            }
        }

        // If no abiotic data available, return moderate score (don't penalize missing data)
        if (scores.length === 0) return 0.5;

        // Average available scores
        return scores.reduce((a, b) => a + b, 0) / scores.length;
    }

    /**
     * Match a value against a "min;max" range string.
     * Returns 0-1 score, or null if can't parse.
     */
    matchRange(rangeStr, value) {
        if (value == null || !rangeStr) return null;
        try {
            const parts = rangeStr.split(';').map(s => parseFloat(s.trim()));
            if (parts.length !== 2 || isNaN(parts[0]) || isNaN(parts[1])) return null;

            const [min, max] = parts;
            if (value >= min && value <= max) return 1.0;

            // Score based on distance to range
            const rangeWidth = Math.max(max - min, 1);
            const dist = value < min ? min - value : value - max;
            return Math.max(0, 1.0 - dist / rangeWidth);
        } catch {
            return null;
        }
    }

    /**
     * Match soil category (semicolon-separated) against a location value.
     */
    matchSoilCategory(speciesPrefs, locationValue) {
        if (!speciesPrefs || !locationValue) return 0.5;

        const prefs = speciesPrefs.toLowerCase().split(';').map(s => s.trim());
        const locVal = locationValue.toLowerCase().trim();

        // Exact match
        if (prefs.some(p => p === locVal)) return 1.0;

        // Partial match (e.g., "sandy loam" matches "loam")
        if (prefs.some(p => locVal.includes(p) || p.includes(locVal))) return 0.7;

        // pH adjacency: moderately acidic ↔ slightly acidic = close match
        const phOrder = ['strongly acidic', 'moderately acidic', 'slightly acidic', 'neutral', 'slightly alkaline', 'moderately alkaline', 'strongly alkaline'];
        const prefIndices = prefs.map(p => phOrder.findIndex(ph => ph === p)).filter(i => i >= 0);
        const locIndex = phOrder.findIndex(ph => ph === locVal);
        if (prefIndices.length > 0 && locIndex >= 0) {
            const minDist = Math.min(...prefIndices.map(i => Math.abs(i - locIndex)));
            return Math.max(0, 1.0 - minDist * 0.25);
        }

        return 0.3; // Unknown match
    }

    // ===========================================================================
    // Component F: Functional Score
    // ===========================================================================

    /**
     * Score trait suitability for the restoration goal.
     */
    computeFunctionalScore(species, strategy, priorities) {
        const traitScores = [];

        const tolerancesText = (species.tolerances_ai || species.tolerances || '').toLowerCase();
        const successionalStage = (species.successional_stage || '').toLowerCase();
        const growthForm = (species.growth_form || species.growth_form_ai || '').toLowerCase();
        const forestLayers = (species.forest_layers || '').toLowerCase();
        const maxHeight = species.maximum_height_ai || species.maximum_height || '';
        const lifespan = (species.lifespan_ai || species.lifespan || '').toLowerCase();
        const agroforestry = (species.agroforestry_use_cases_ai || '').toLowerCase();
        const timberValue = (species.timber_value || species.timber_value_ai || '').toLowerCase();
        const ntfp = (species.non_timber_products || species.non_timber_products_ai || '').toLowerCase();

        // Count GloBI interactions
        const globiFields = [
            species.globi_pollinatedby, species.globi_eatenby,
            species.globi_flowersvisitedby, species.globi_hasdispersalvector,
            species.globi_hasparasite, species.globi_haspathogen,
            species.globi_preyeduponby, species.globi_hasparasitoid
        ];
        const interactionCount = globiFields.filter(f => f && f !== 'NA' && f.length > 2).length;

        // Strategy-specific trait scoring
        switch (strategy) {
            case 'rewilding':
                if (successionalStage.includes('late') || successionalStage.includes('climax'))
                    traitScores.push({ score: 1.0, weight: 0.3 });
                else if (successionalStage.includes('mid'))
                    traitScores.push({ score: 0.7, weight: 0.3 });

                if (tolerancesText.includes('shade'))
                    traitScores.push({ score: 1.0, weight: 0.2 });

                traitScores.push({ score: Math.min(1.0, interactionCount / 5), weight: 0.3 });

                if (forestLayers.includes('canopy') || forestLayers.includes('emergent'))
                    traitScores.push({ score: 1.0, weight: 0.2 });
                break;

            case 'agroforestry':
                // Multi-use (agroforestry mentions, NTFP)
                if (agroforestry && agroforestry !== 'na' && agroforestry.length > 5)
                    traitScores.push({ score: 1.0, weight: 0.3 });
                else if (ntfp && ntfp !== 'na' && ntfp.length > 5)
                    traitScores.push({ score: 0.8, weight: 0.3 });

                // Food production
                if (agroforestry.includes('fruit') || agroforestry.includes('food') || agroforestry.includes('nut'))
                    traitScores.push({ score: 1.0, weight: 0.3 });

                // Nitrogen fixing
                if (tolerancesText.includes('nitrogen') || agroforestry.includes('nitrogen'))
                    traitScores.push({ score: 1.0, weight: 0.2 });

                // Fast growth
                if (successionalStage.includes('pioneer') || successionalStage.includes('early'))
                    traitScores.push({ score: 0.8, weight: 0.2 });
                break;

            case 'riparian':
                if (tolerancesText.includes('flood') || tolerancesText.includes('waterlog'))
                    traitScores.push({ score: 1.0, weight: 0.35 });

                if (tolerancesText.includes('wet') || tolerancesText.includes('riparian'))
                    traitScores.push({ score: 1.0, weight: 0.25 });

                if (tolerancesText.includes('erosion') || tolerancesText.includes('bank'))
                    traitScores.push({ score: 1.0, weight: 0.2 });
                break;

            case 'carbon':
                // Tall tree
                const heightNum = parseFloat(maxHeight);
                if (!isNaN(heightNum)) {
                    traitScores.push({ score: Math.min(1.0, heightNum / 40), weight: 0.3 });
                } else if (growthForm.includes('tree')) {
                    traitScores.push({ score: 0.6, weight: 0.3 });
                }

                // Long-lived
                if (lifespan.includes('long') || lifespan.includes('centuries') || lifespan.includes('500'))
                    traitScores.push({ score: 1.0, weight: 0.25 });
                else if (lifespan.includes('decades') || lifespan.includes('100'))
                    traitScores.push({ score: 0.6, weight: 0.25 });

                // Timber value = dense wood = high carbon storage
                if (timberValue && timberValue !== 'na' && timberValue.length > 5)
                    traitScores.push({ score: 0.8, weight: 0.2 });
                break;

            case 'biodiversity':
                // Interaction richness
                traitScores.push({ score: Math.min(1.0, interactionCount / 5), weight: 0.3 });

                // Structural diversity (different layers)
                if (forestLayers && forestLayers !== 'na') {
                    const layerCount = forestLayers.split(';').filter(l => l.trim().length > 2).length;
                    traitScores.push({ score: Math.min(1.0, layerCount / 3), weight: 0.2 });
                }

                // Keystone potential (many species eat/pollinate it)
                const dependents = [species.globi_pollinatedby, species.globi_eatenby, species.globi_flowersvisitedby]
                    .filter(f => f && f !== 'NA')
                    .join(';')
                    .split(';')
                    .filter(s => s.trim().length > 2).length;
                traitScores.push({ score: Math.min(1.0, dependents / 10), weight: 0.2 });
                break;

            case 'erosion_control':
                // Pioneer/fast establishing
                if (successionalStage.includes('pioneer') || successionalStage.includes('early'))
                    traitScores.push({ score: 1.0, weight: 0.3 });

                // Drought tolerance
                if (tolerancesText.includes('drought'))
                    traitScores.push({ score: 1.0, weight: 0.2 });

                // Ground cover / understory
                if (forestLayers.includes('understory') || forestLayers.includes('ground'))
                    traitScores.push({ score: 1.0, weight: 0.2 });
                break;

            default: // general
                if (growthForm.includes('tree'))
                    traitScores.push({ score: 0.7, weight: 1.0 });
                break;
        }

        if (traitScores.length === 0) return 0.4; // Default for unknown traits

        const totalWeight = traitScores.reduce((sum, t) => sum + t.weight, 0);
        const weighted = traitScores.reduce((sum, t) => sum + t.score * t.weight, 0);
        return weighted / Math.max(totalWeight, 0.01);
    }

    // ===========================================================================
    // Component E: Ecosystem Score
    // ===========================================================================

    /**
     * Score ecoregion, biome, and functional ecosystem group match.
     * Supports partial credit for spatially-confirmed species (plantation/introduced species
     * whose ecoregion DB entry only lists native range).
     */
    computeEcosystemScore(species, locationContext, spatialTileCount = 0) {
        const scores = [];

        // Ecoregion match
        if (locationContext.ecoregion && species.ecoregions) {
            const speciesEcoregions = species.ecoregions.toLowerCase();
            const locationEcoName = locationContext.ecoregion.eco_name.toLowerCase();

            if (speciesEcoregions.includes(locationEcoName.substring(0, 15))) {
                scores.push(1.0);
            } else if (spatialTileCount >= 10) {
                // Spatially-confirmed species get partial ecoregion credit even if not listed
                // (common for introduced/plantation species)
                scores.push(0.5);
            } else if (spatialTileCount >= 3) {
                scores.push(0.25);
            } else {
                scores.push(0.0);
            }
        }

        // Biome match
        if (locationContext.ecoregion?.biome_name && species.biomes) {
            const speciesBiomes = species.biomes.toLowerCase();
            const locationBiome = locationContext.ecoregion.biome_name.toLowerCase();

            if (speciesBiomes.includes(locationBiome.substring(0, 15))) {
                scores.push(1.0);
            } else if (spatialTileCount >= 10) {
                scores.push(0.4); // Partial biome credit for spatial confirmation
            } else {
                scores.push(0.0);
            }
        }

        // Realm match (broad geographic region)
        if (locationContext.ecoregion?.realm && species.bioregions) {
            const speciesRealms = species.bioregions.toLowerCase();
            const locationRealm = locationContext.ecoregion.realm.toLowerCase();

            if (speciesRealms.includes(locationRealm.substring(0, 10))) {
                scores.push(0.8);
            } else {
                scores.push(0.1);
            }
        }

        if (scores.length === 0) return 0.3; // Unknown

        return scores.reduce((a, b) => a + b, 0) / scores.length;
    }

    // ===========================================================================
    // Component B: Biotic Score
    // ===========================================================================

    /**
     * Score based on GloBI interaction network richness.
     * Species with more ecological interactions are more ecologically integrated.
     */
    computeBioticScore(species) {
        const fields = [
            { name: 'pollinatedby', data: species.globi_pollinatedby, weight: 2.0 },
            { name: 'dispersalvector', data: species.globi_hasdispersalvector, weight: 1.5 },
            { name: 'flowersvisitedby', data: species.globi_flowersvisitedby, weight: 1.0 },
            { name: 'eatenby', data: species.globi_eatenby, weight: 0.8 },
            { name: 'hasparasite', data: species.globi_hasparasite, weight: 0.3 },
            { name: 'haspathogen', data: species.globi_haspathogen, weight: 0.2 },
            { name: 'preyeduponby', data: species.globi_preyeduponby, weight: 0.5 },
            { name: 'hasparasitoid', data: species.globi_hasparasitoid, weight: 0.3 }
        ];

        let totalScore = 0;
        let totalWeight = 0;

        for (const field of fields) {
            if (field.data && field.data !== 'NA' && field.data.length > 2) {
                // Count unique interaction partners
                const partners = field.data.split(';').filter(s => s.trim().length > 2).length;
                // Normalize: 5+ partners = full score
                const partnerScore = Math.min(1.0, partners / 5);
                totalScore += partnerScore * field.weight;
            }
            totalWeight += field.weight;
        }

        if (totalWeight === 0) return 0.3; // Default for unknown
        return totalScore / totalWeight;
    }

    // ===========================================================================
    // Native Status Assessment
    // ===========================================================================

    assessNativeStatus(species, locationContext) {
        const wcvpNative = (species.wcvp_native || '').toLowerCase();
        const wcvpIntroduced = (species.wcvp_introduced || '').toLowerCase();
        const countriesInvasive = (species.countries_invasive || '').toLowerCase();

        const patterns = locationContext.wcvpPatterns || [];

        const isNative = patterns.length > 0 && patterns.some(p => wcvpNative.includes(p));
        const isIntroduced = patterns.length > 0 && patterns.some(p => wcvpIntroduced.includes(p));
        const isInvasive = locationContext.countries?.length > 0 &&
            locationContext.countries.some(c => countriesInvasive.includes(c.toLowerCase()));

        let status = 'unknown';
        if (isInvasive) status = 'invasive';
        else if (isNative && !isIntroduced) status = 'native';
        else if (isIntroduced && !isNative) status = 'introduced';
        else if (isNative && isIntroduced) status = 'native_and_introduced';

        return { status, isNative, isIntroduced, isInvasive };
    }
}

// Export
module.exports = {
    SafeBScorer,
    STRATEGY_WEIGHTS,
    FUNCTIONAL_PRIORITIES
};
