/**
 * Grok 4.1 Fast Research Service
 *
 * AI research for tree species using xAI's Grok API with agentic web search.
 * Includes confidence scoring and source extraction for insights architecture.
 */

const axios = require('axios');

const XAI_API_KEY = process.env.XAI_API_KEY;
const XAI_RESPONSES_URL = 'https://api.x.ai/v1/responses';
const MODEL = 'grok-4-1-fast-reasoning';

// All 25 research fields
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

// Critical fields that should have higher weight in confidence calculation
const CRITICAL_FIELDS = [
  'general_description_ai',
  'habitat_ai',
  'ecological_function_ai',
  'conservation_status_ai',
  'native_adapted_habitats_ai'
];

/**
 * Build the research prompt for a species
 */
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

/**
 * Extract text content from Grok API response
 */
function extractResponseText(responseData) {
  let outputText = '';

  // Check output array for message type with output_text content
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
 * Grok returns tool_use blocks with web_search results
 */
function extractSources(responseData) {
  const sources = [];

  if (responseData.output && Array.isArray(responseData.output)) {
    for (const item of responseData.output) {
      // Look for tool_use blocks with web_search
      if (item.type === 'tool_use' && item.name === 'web_search') {
        // Extract search queries as implicit sources
        if (item.input && item.input.query) {
          sources.push({
            type: 'web_search',
            query: item.input.query,
            timestamp: new Date().toISOString()
          });
        }
      }
      // Look for tool_result blocks with actual URLs/citations
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

/**
 * Calculate confidence score based on research quality
 *
 * Factors:
 * - Percentage of fields filled (40% weight)
 * - Critical fields filled (30% weight)
 * - Data specificity - longer responses indicate more detail (20% weight)
 * - Number of sources used (10% weight)
 */
function calculateConfidence(normalizedData, filledFields, sources) {
  // Factor 1: Overall field coverage (40%)
  const fieldCoverageScore = filledFields / RESEARCH_FIELDS.length;

  // Factor 2: Critical field coverage (30%)
  const criticalFilled = CRITICAL_FIELDS.filter(f =>
    normalizedData[f] &&
    normalizedData[f] !== 'Data not available' &&
    normalizedData[f] !== null
  ).length;
  const criticalScore = criticalFilled / CRITICAL_FIELDS.length;

  // Factor 3: Data specificity - average content length (20%)
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
  // Scale: 0-50 chars = 0.0, 50-200 chars = 0.5, 200+ chars = 1.0
  const specificityScore = Math.min(1.0, Math.max(0, (avgLength - 50) / 150));

  // Factor 4: Source count (10%)
  // Scale: 0 sources = 0.5 (baseline for web search), 1-3 = 0.7, 4+ = 1.0
  const sourceScore = sources.length === 0 ? 0.5
    : sources.length <= 3 ? 0.7
    : 1.0;

  // Weighted calculation
  const confidence =
    (fieldCoverageScore * 0.40) +
    (criticalScore * 0.30) +
    (specificityScore * 0.20) +
    (sourceScore * 0.10);

  return Math.round(confidence * 100) / 100; // Round to 2 decimal places
}

/**
 * Generate confidence breakdown for transparency
 */
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

/**
 * Normalize numeric fields to proper types
 */
function normalizeData(data) {
  const normalized = { ...data };

  // Ensure all fields exist
  RESEARCH_FIELDS.forEach(field => {
    if (!(field in normalized) || normalized[field] === null || normalized[field] === undefined) {
      normalized[field] = null;
    }
  });

  // Convert numeric fields
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

/**
 * Perform AI research for a species
 *
 * @param {string} scientificName - Scientific name of the species
 * @param {string} commonNames - Common names (comma-separated)
 * @returns {Promise<{success: boolean, data?: object, error?: string, usage?: object, confidence?: number, sources?: array}>}
 */
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
      timeout: 120000 // 2 minute timeout
    });

    const duration = Date.now() - startTime;
    console.log(`[GrokResearch] API response received in ${duration}ms`);

    if (!response.data) {
      return { success: false, error: 'Empty response from API' };
    }

    // Extract sources from web search tool usage
    const sources = extractSources(response.data);
    console.log(`[GrokResearch] Extracted ${sources.length} sources from response`);

    // Extract text from response
    const outputText = extractResponseText(response.data);

    if (!outputText) {
      return { success: false, error: 'No text content in response' };
    }

    // Parse JSON from response
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

    // Normalize the data
    const normalizedData = normalizeData(parsedData);

    // Count filled fields
    const filledFields = RESEARCH_FIELDS.filter(f =>
      normalizedData[f] &&
      normalizedData[f] !== 'Data not available' &&
      normalizedData[f] !== null
    ).length;

    // Calculate confidence score
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
  RESEARCH_FIELDS,
  CRITICAL_FIELDS
};
