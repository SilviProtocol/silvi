/**
 * Grok 4.1 Fast Research Service
 *
 * AI research for tree species using xAI's Grok API with agentic web search.
 * Includes confidence scoring and source extraction for insights architecture.
 *
 * v2: Atomic insights via two parallel Grok calls covering 35 fields.
 */

const axios = require('axios');

const XAI_API_KEY = process.env.XAI_API_KEY;
const XAI_RESPONSES_URL = 'https://api.x.ai/v1/responses';
const MODEL = 'grok-4-1-fast-reasoning';

// ============================================================================
// LEGACY (v1) — kept for backward compatibility
// ============================================================================

// All 25 original research fields
const RESEARCH_FIELDS = [
  'popular_common_name_ai',
  'habitat_ai', 'elevation_ranges_ai', 'ecological_function_ai', 'native_adapted_habitats_ai',
  'agroforestry_use_cases_ai', 'conservation_status_ai', 'general_description_ai', 'compatible_soil_types_ai',
  'growth_form_ai', 'leaf_type_ai', 'deciduous_evergreen_ai', 'flower_color_ai',
  'fruit_type_ai', 'bark_characteristics_ai', 'maximum_height_ai', 'maximum_diameter_ai',
  'lifespan_ai', 'maximum_tree_age_ai',
  'stewardship_best_practices_ai', 'planting_recipes_ai', 'pruning_maintenance_ai',
  'disease_pest_management_ai', 'fire_management_ai', 'cultural_significance_ai'
];

const CRITICAL_FIELDS = [
  'general_description_ai',
  'habitat_ai',
  'ecological_function_ai',
  'conservation_status_ai',
  'native_adapted_habitats_ai'
];

// ============================================================================
// ATOMIC (v2) — two parallel calls, 35 fields, array support
// ============================================================================

/**
 * Call 1 — Identity + Ecological (14 fields)
 * Each entry: { name, type, multi, description }
 */
const CALL_1_FIELDS = [
  { name: 'popular_common_name', type: 'string', multi: false, desc: 'The single most widely-used common English name' },
  { name: 'etymology', type: 'string', multi: false, desc: 'Origin and meaning of the scientific and common names' },
  { name: 'general_description', type: 'string', multi: false, desc: 'Comprehensive botanical description (2-4 sentences)' },
  { name: 'conservation_status', type: 'string', multi: false, desc: 'IUCN Red List status with assessment year (e.g. "Vulnerable (VU) - IUCN 2023")' },
  { name: 'elevation_ranges', type: 'string', multi: false, desc: 'Elevation range in meters (e.g. "100-1500m")' },
  { name: 'compatible_soil_types', type: 'string', multi: false, desc: 'Soil types and pH preferences' },
  { name: 'climate_tolerance', type: 'string', multi: false, desc: 'Temperature, rainfall, and climate zone tolerances' },
  { name: 'synonyms', type: 'string', multi: false, desc: 'Taxonomic synonyms (semicolon-separated scientific names)' },
  { name: 'identification_features', type: 'string', multi: false, desc: 'Key diagnostic features for field identification' },
  { name: 'habitat', type: 'array', multi: true, desc: 'Distinct habitat types. One entry per habitat. Aim for 3-5.' },
  { name: 'ecological_function', type: 'array', multi: true, desc: 'Distinct ecological roles (nitrogen fixation, wildlife habitat, etc.). Aim for 3-5.' },
  { name: 'native_adapted_habitats', type: 'array', multi: true, desc: 'Distinct native range regions and adapted habitats. One entry per region/habitat.' },
  { name: 'tolerances', type: 'array', multi: true, desc: 'Specific tolerances (drought, salt, frost, wind, pollution, etc.). One per tolerance.' },
  { name: 'associated_species', type: 'array', multi: true, desc: 'Tree/plant species commonly found growing with this species. One per species.' }
];

/**
 * Call 2 — Morphological + Stewardship (21 fields)
 */
const CALL_2_FIELDS = [
  { name: 'growth_form', type: 'string', multi: false, desc: 'Growth form and structure (e.g. "Single-stemmed tree with broad spreading crown")' },
  { name: 'leaf_type', type: 'string', multi: false, desc: 'Leaf characteristics and morphology' },
  { name: 'deciduous_evergreen', type: 'string', multi: false, desc: '"deciduous", "evergreen", or "semi-deciduous"' },
  { name: 'flower_color', type: 'string', multi: false, desc: 'Flower colors and bloom season' },
  { name: 'fruit_type', type: 'string', multi: false, desc: 'Fruit type and characteristics' },
  { name: 'bark_characteristics', type: 'string', multi: false, desc: 'Bark appearance and texture' },
  { name: 'maximum_height', type: 'number', multi: false, desc: 'Maximum height in meters. NUMBER ONLY, no units.' },
  { name: 'maximum_diameter', type: 'number', multi: false, desc: 'Maximum trunk diameter in meters. NUMBER ONLY, no units.' },
  { name: 'lifespan', type: 'string', multi: false, desc: 'Typical lifespan description' },
  { name: 'maximum_tree_age', type: 'number', multi: false, desc: 'Maximum recorded age in years. INTEGER ONLY.' },
  { name: 'planting_recipes', type: 'string', multi: false, desc: 'Planting requirements and techniques' },
  { name: 'pruning_maintenance', type: 'string', multi: false, desc: 'Pruning and maintenance practices' },
  { name: 'fire_management', type: 'string', multi: false, desc: 'Fire tolerance and management' },
  { name: 'propagation_methods', type: 'string', multi: false, desc: 'Propagation methods (seed, cutting, grafting, etc.)' },
  { name: 'timber_value', type: 'string', multi: false, desc: 'Timber properties and commercial value' },
  { name: 'nutritional_caloric_value', type: 'string', multi: false, desc: 'Nutritional/caloric value of edible parts, if any' },
  { name: 'stewardship_best_practices', type: 'array', multi: true, desc: 'Distinct cultivation and care practices. One per practice.' },
  { name: 'disease_pest_management', type: 'array', multi: true, desc: 'Distinct diseases/pests and their management. One per disease/pest.' },
  { name: 'cultural_significance', type: 'array', multi: true, desc: 'Distinct cultural, traditional, or ceremonial uses. One per use.' },
  { name: 'agroforestry_use_cases', type: 'array', multi: true, desc: 'Distinct agroforestry applications. One per use case.' },
  { name: 'non_timber_products', type: 'array', multi: true, desc: 'Distinct non-timber forest products (resin, fruit, medicine, etc.). One per product.' }
];

/**
 * Build an atomic prompt for one field group
 */
function buildAtomicPrompt(scientificName, commonNames, fieldGroup) {
  const fieldLines = fieldGroup.map(f => {
    const typeLabel = f.type === 'array' ? 'ARRAY' : f.type === 'number' ? 'NUMBER' : 'STRING';
    return `- ${f.name}: ${typeLabel}. ${f.desc}`;
  }).join('\n');

  return `You are a botanical research expert. Research the tree species "${scientificName}" (commonly known as: ${commonNames || 'various names'}).

Return a JSON object with the fields listed below.

TYPE RULES:
- STRING fields: return a string value.
- NUMBER fields: return ONLY a number (no units, no text).
- ARRAY fields: return an array of objects, each with:
  {text: "distinct fact", context: "category/label", region: "geographic scope (optional)", source_hint: "source name (optional)"}
  Aim for 3-5 entries per array field where data exists. Each entry must be a DISTINCT fact.

FIELDS:
${fieldLines}

EXAMPLE (partial):
{
  "habitat": [
    {"text": "Tropical lowland rainforest below 500m", "context": "primary habitat", "region": "SE Asia", "source_hint": "Flora Malesiana"},
    {"text": "Riparian zones along rivers", "context": "secondary habitat", "source_hint": "IUCN"}
  ],
  "conservation_status": "Vulnerable (VU) - IUCN 2023",
  "maximum_height": 45
}

RULES:
1. Search thoroughly for EACH field using web search
2. Array entries must be DISTINCT facts, not reformulations of the same fact
3. "Data not available" only as absolute last resort after extensive searching
4. source_hint is optional — use the name of the database/publication you found the fact in
5. Return ONLY valid JSON, no markdown or additional text
6. Be species-specific — avoid generic tree information`;
}

/**
 * Make a single Grok API call and parse the result
 */
async function callGrokAtomic(prompt, callLabel) {
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${XAI_API_KEY}`
  };

  const payload = {
    model: MODEL,
    input: prompt,
    tools: [{ type: 'web_search' }]
  };

  const startTime = Date.now();
  console.log(`[GrokResearch] ${callLabel}: Starting API call`);

  const response = await axios.post(XAI_RESPONSES_URL, payload, {
    headers,
    timeout: 120000
  });

  const duration = Date.now() - startTime;
  console.log(`[GrokResearch] ${callLabel}: Response received in ${duration}ms`);

  if (!response.data) {
    throw new Error('Empty response from API');
  }

  const sources = extractSources(response.data);
  const outputText = extractResponseText(response.data);

  if (!outputText) {
    throw new Error('No text content in response');
  }

  const jsonMatch = outputText.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error('No JSON found in response');
  }

  let parsedData;
  try {
    parsedData = JSON.parse(jsonMatch[0]);
  } catch (parseError) {
    throw new Error(`JSON parsing failed: ${parseError.message}`);
  }

  return {
    data: parsedData,
    sources,
    usage: response.data.usage || {},
    duration_ms: duration
  };
}

/**
 * Perform atomic research — two parallel Grok calls covering all 35 fields
 *
 * @param {string} scientificName
 * @param {string} commonNames
 * @returns {Promise<{success, fields, sources, usage, model, duration_ms, calls_succeeded, partial}>}
 */
async function performAtomicResearch(scientificName, commonNames) {
  if (!XAI_API_KEY) {
    return { success: false, error: 'XAI_API_KEY not configured' };
  }

  const prompt1 = buildAtomicPrompt(scientificName, commonNames, CALL_1_FIELDS);
  const prompt2 = buildAtomicPrompt(scientificName, commonNames, CALL_2_FIELDS);

  const startTime = Date.now();
  console.log(`[GrokResearch] Starting atomic research for: ${scientificName} (2 parallel calls)`);

  const [result1, result2] = await Promise.allSettled([
    callGrokAtomic(prompt1, 'Call1-Identity+Ecological'),
    callGrokAtomic(prompt2, 'Call2-Morphological+Stewardship')
  ]);

  const duration = Date.now() - startTime;
  const callsSucceeded = [result1, result2].filter(r => r.status === 'fulfilled').length;

  if (callsSucceeded === 0) {
    const errors = [result1, result2].map(r => r.reason?.message || 'Unknown error').join('; ');
    console.error(`[GrokResearch] Both calls failed: ${errors}`);
    return { success: false, error: `Both calls failed: ${errors}`, duration_ms: duration };
  }

  // Merge fields from successful calls
  const mergedFields = {};
  const allSources = [];
  let totalInputTokens = 0;
  let totalOutputTokens = 0;

  if (result1.status === 'fulfilled') {
    Object.assign(mergedFields, result1.value.data);
    allSources.push(...result1.value.sources);
    totalInputTokens += result1.value.usage.input_tokens || 0;
    totalOutputTokens += result1.value.usage.output_tokens || 0;
  } else {
    console.warn(`[GrokResearch] Call 1 failed: ${result1.reason?.message}`);
  }

  if (result2.status === 'fulfilled') {
    Object.assign(mergedFields, result2.value.data);
    allSources.push(...result2.value.sources);
    totalInputTokens += result2.value.usage.input_tokens || 0;
    totalOutputTokens += result2.value.usage.output_tokens || 0;
  } else {
    console.warn(`[GrokResearch] Call 2 failed: ${result2.reason?.message}`);
  }

  const allFieldDefs = [...CALL_1_FIELDS, ...CALL_2_FIELDS];
  const filledCount = allFieldDefs.filter(f => {
    const v = mergedFields[f.name];
    if (v === null || v === undefined || v === '' || v === 'Data not available') return false;
    if (Array.isArray(v) && v.length === 0) return false;
    return true;
  }).length;

  console.log(`[GrokResearch] Atomic research complete: ${filledCount}/${allFieldDefs.length} fields, ${callsSucceeded}/2 calls succeeded, ${duration}ms`);

  return {
    success: true,
    fields: mergedFields,
    sources: allSources,
    usage: { input_tokens: totalInputTokens, output_tokens: totalOutputTokens },
    model: MODEL,
    duration_ms: duration,
    calls_succeeded: callsSucceeded,
    partial: callsSucceeded < 2,
    fields_filled: filledCount,
    fields_total: allFieldDefs.length
  };
}

// ============================================================================
// SHARED UTILITIES
// ============================================================================

/**
 * Extract text content from Grok API response
 */
function extractResponseText(responseData) {
  let outputText = '';

  if (responseData.output && Array.isArray(responseData.output)) {
    for (const item of responseData.output) {
      if (item.type === 'message' && item.content) {
        if (typeof item.content === 'string') {
          outputText += item.content;
        } else if (Array.isArray(item.content)) {
          for (const block of item.content) {
            if (block.type === 'output_text' && block.text) {
              outputText += block.text;
            } else if (block.type === 'text' && block.text) {
              outputText += block.text;
            }
          }
        }
      }
    }
  }

  return outputText;
}

/**
 * Extract web search sources from Grok API response
 */
function extractSources(responseData) {
  const sources = [];

  if (responseData.output && Array.isArray(responseData.output)) {
    for (const item of responseData.output) {
      if (item.type === 'tool_use' && item.name === 'web_search') {
        if (item.input && item.input.query) {
          sources.push({
            type: 'web_search',
            query: item.input.query,
            timestamp: new Date().toISOString()
          });
        }
      }
      if (item.type === 'tool_result' && item.content) {
        try {
          const content = typeof item.content === 'string'
            ? JSON.parse(item.content)
            : item.content;

          if (Array.isArray(content)) {
            for (const result of content) {
              if (result.url || result.title) {
                sources.push({
                  type: 'web_result',
                  url: result.url || null,
                  title: result.title || null,
                  snippet: result.snippet || result.description || null
                });
              }
            }
          }
        } catch (e) {
          // Content wasn't parseable JSON, skip
        }
      }
    }
  }

  return sources;
}

// ============================================================================
// LEGACY performResearch (v1) — kept for backward compatibility
// ============================================================================

function buildPrompt(scientificName, commonNames) {
  return `You are a botanical research expert. Research the tree species "${scientificName}" (commonly known as: ${commonNames || 'various names'}) and provide comprehensive data for ALL of the following fields.

SEARCH EXTENSIVELY using web search. Use multiple searches if needed to find accurate, species-specific information. Cross-reference multiple sources.

Return a JSON object with these exact field names:

**Identity (1 field):**
- popular_common_name_ai: The single most widely-used common name for this species in English (just one name, the most popular/recognized)

**Ecological & General (8 fields):**
- habitat_ai: Natural habitat and ecosystem types
- elevation_ranges_ai: Elevation range in meters (e.g., "100-1500" or specific range)
- ecological_function_ai: Ecological roles in its ecosystem
- native_adapted_habitats_ai: Original native range and adapted habitats
- agroforestry_use_cases_ai: Applications in agroforestry
- conservation_status_ai: IUCN or official conservation status
- general_description_ai: Comprehensive botanical description
- compatible_soil_types_ai: Soil types and pH preferences

**Morphological (10 fields):**
- growth_form_ai: Growth form and structure
- leaf_type_ai: Leaf characteristics and morphology
- deciduous_evergreen_ai: "deciduous", "evergreen", or "semi-deciduous"
- flower_color_ai: Flower colors
- fruit_type_ai: Fruit type and characteristics
- bark_characteristics_ai: Bark appearance and texture
- maximum_height_ai: Maximum height in meters (NUMBER ONLY, no units)
- maximum_diameter_ai: Maximum trunk diameter in meters (NUMBER ONLY, no units)
- lifespan_ai: Typical lifespan description
- maximum_tree_age_ai: Maximum recorded age in years (INTEGER ONLY)

**Stewardship (6 fields):**
- stewardship_best_practices_ai: Cultivation and care practices
- planting_recipes_ai: Planting requirements and techniques
- pruning_maintenance_ai: Pruning and maintenance practices
- disease_pest_management_ai: Common diseases, pests, and management
- fire_management_ai: Fire tolerance and management
- cultural_significance_ai: Cultural, traditional, or ceremonial significance

CRITICAL INSTRUCTIONS:
1. Search thoroughly for EACH field before marking as unavailable
2. For numeric fields (maximum_height_ai, maximum_diameter_ai, maximum_tree_age_ai), return ONLY the number
3. Use "Data not available" ONLY as absolute last resort after extensive searching
4. Be species-specific - avoid generic tree information
5. Return ONLY valid JSON, no additional text

Example format:
{
  "popular_common_name_ai": "Maidenhair tree",
  "habitat_ai": "Temperate forests...",
  "maximum_height_ai": 35,
  "maximum_tree_age_ai": 1000,
  ...
}`;
}

function calculateConfidence(normalizedData, filledFields, sources) {
  const fieldCoverageScore = filledFields / RESEARCH_FIELDS.length;
  const criticalFilled = CRITICAL_FIELDS.filter(f =>
    normalizedData[f] &&
    normalizedData[f] !== 'Data not available' &&
    normalizedData[f] !== null
  ).length;
  const criticalScore = criticalFilled / CRITICAL_FIELDS.length;

  let totalLength = 0;
  let textFieldCount = 0;
  for (const field of RESEARCH_FIELDS) {
    const value = normalizedData[field];
    if (value && typeof value === 'string' && value !== 'Data not available') {
      totalLength += value.length;
      textFieldCount++;
    }
  }
  const avgLength = textFieldCount > 0 ? totalLength / textFieldCount : 0;
  const specificityScore = Math.min(1.0, Math.max(0, (avgLength - 50) / 150));

  const sourceScore = sources.length === 0 ? 0.5
    : sources.length <= 3 ? 0.7
    : 1.0;

  const confidence =
    (fieldCoverageScore * 0.40) +
    (criticalScore * 0.30) +
    (specificityScore * 0.20) +
    (sourceScore * 0.10);

  return Math.round(confidence * 100) / 100;
}

function getConfidenceBreakdown(normalizedData, filledFields, sources) {
  const criticalFilled = CRITICAL_FIELDS.filter(f =>
    normalizedData[f] &&
    normalizedData[f] !== 'Data not available' &&
    normalizedData[f] !== null
  ).length;

  let totalLength = 0;
  let textFieldCount = 0;
  for (const field of RESEARCH_FIELDS) {
    const value = normalizedData[field];
    if (value && typeof value === 'string' && value !== 'Data not available') {
      totalLength += value.length;
      textFieldCount++;
    }
  }

  return {
    field_coverage: {
      score: Math.round((filledFields / RESEARCH_FIELDS.length) * 100) / 100,
      filled: filledFields,
      total: RESEARCH_FIELDS.length,
      weight: 0.40
    },
    critical_fields: {
      score: Math.round((criticalFilled / CRITICAL_FIELDS.length) * 100) / 100,
      filled: criticalFilled,
      total: CRITICAL_FIELDS.length,
      weight: 0.30
    },
    specificity: {
      score: Math.round(Math.min(1.0, Math.max(0, ((totalLength / Math.max(1, textFieldCount)) - 50) / 150)) * 100) / 100,
      avg_length: textFieldCount > 0 ? Math.round(totalLength / textFieldCount) : 0,
      weight: 0.20
    },
    sources: {
      score: sources.length === 0 ? 0.5 : sources.length <= 3 ? 0.7 : 1.0,
      count: sources.length,
      weight: 0.10
    },
    methodology: 'grok-web-search: field_coverage × 40% + critical_fields × 30% + specificity × 20% + sources × 10%'
  };
}

function normalizeData(data) {
  const normalized = { ...data };

  RESEARCH_FIELDS.forEach(field => {
    if (!(field in normalized) || normalized[field] === null || normalized[field] === undefined) {
      normalized[field] = null;
    }
  });

  if (normalized.maximum_height_ai && typeof normalized.maximum_height_ai === 'string') {
    const height = parseFloat(normalized.maximum_height_ai);
    normalized.maximum_height_ai = isNaN(height) ? null : height;
  }
  if (normalized.maximum_diameter_ai && typeof normalized.maximum_diameter_ai === 'string') {
    const diameter = parseFloat(normalized.maximum_diameter_ai);
    normalized.maximum_diameter_ai = isNaN(diameter) ? null : diameter;
  }
  if (normalized.maximum_tree_age_ai && typeof normalized.maximum_tree_age_ai === 'string') {
    const age = parseInt(normalized.maximum_tree_age_ai);
    normalized.maximum_tree_age_ai = isNaN(age) ? null : age;
  }

  return normalized;
}

async function performResearch(scientificName, commonNames) {
  if (!XAI_API_KEY) {
    return { success: false, error: 'XAI_API_KEY not configured' };
  }

  const prompt = buildPrompt(scientificName, commonNames);

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${XAI_API_KEY}`
  };

  const payload = {
    model: MODEL,
    input: prompt,
    tools: [{ type: 'web_search' }]
  };

  const startTime = Date.now();

  try {
    console.log(`[GrokResearch] Starting research for: ${scientificName}`);

    const response = await axios.post(XAI_RESPONSES_URL, payload, {
      headers,
      timeout: 120000
    });

    const duration = Date.now() - startTime;
    console.log(`[GrokResearch] API response received in ${duration}ms`);

    if (!response.data) {
      return { success: false, error: 'Empty response from API' };
    }

    const sources = extractSources(response.data);
    console.log(`[GrokResearch] Extracted ${sources.length} sources from response`);

    const outputText = extractResponseText(response.data);

    if (!outputText) {
      return { success: false, error: 'No text content in response' };
    }

    const jsonMatch = outputText.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return { success: false, error: 'No JSON found in response' };
    }

    let parsedData;
    try {
      parsedData = JSON.parse(jsonMatch[0]);
    } catch (parseError) {
      return { success: false, error: `JSON parsing failed: ${parseError.message}` };
    }

    const normalizedData = normalizeData(parsedData);

    const filledFields = RESEARCH_FIELDS.filter(f =>
      normalizedData[f] &&
      normalizedData[f] !== 'Data not available' &&
      normalizedData[f] !== null
    ).length;

    const confidence = calculateConfidence(normalizedData, filledFields, sources);
    const confidenceBreakdown = getConfidenceBreakdown(normalizedData, filledFields, sources);

    console.log(`[GrokResearch] Completed: ${filledFields}/${RESEARCH_FIELDS.length} fields filled, confidence: ${confidence}`);

    return {
      success: true,
      data: normalizedData,
      usage: response.data.usage,
      duration_ms: duration,
      fields_filled: filledFields,
      fields_total: RESEARCH_FIELDS.length,
      confidence: confidence,
      confidence_breakdown: confidenceBreakdown,
      sources: sources,
      model: MODEL
    };

  } catch (error) {
    const duration = Date.now() - startTime;
    console.error(`[GrokResearch] Error after ${duration}ms:`, error.response?.data || error.message);

    return {
      success: false,
      error: error.response?.data?.error?.message || error.message,
      duration_ms: duration
    };
  }
}

module.exports = {
  performResearch,
  performAtomicResearch,
  RESEARCH_FIELDS,
  CRITICAL_FIELDS,
  CALL_1_FIELDS,
  CALL_2_FIELDS
};
