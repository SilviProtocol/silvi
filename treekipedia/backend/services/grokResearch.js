/**
 * Grok 4.1 Fast Research Service
 *
 * Simple, clean AI research for tree species using xAI's Grok API
 * with agentic web search capabilities.
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
 * @returns {Promise<{success: boolean, data?: object, error?: string, usage?: object}>}
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

    console.log(`[GrokResearch] Completed: ${filledFields}/${RESEARCH_FIELDS.length} fields filled`);

    return {
      success: true,
      data: normalizedData,
      usage: response.data.usage,
      duration_ms: duration,
      fields_filled: filledFields,
      fields_total: RESEARCH_FIELDS.length
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
  RESEARCH_FIELDS
};
