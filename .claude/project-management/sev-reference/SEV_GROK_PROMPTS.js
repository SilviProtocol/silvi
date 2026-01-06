#!/usr/bin/env node

/**
 * Grok 4.1 Fast Agentic API Testing Script
 *
 * Tests the xAI Responses API with agentic web_search tool for tree species research.
 * Compares:
 *   - Model variants: grok-4-1-fast-reasoning vs grok-4-1-fast-non-reasoning
 *   - Strategies: single comprehensive call vs 3-group parallel calls
 */

const fs = require('fs');
const path = require('path');
const axios = require('axios');
require('dotenv').config({ path: path.join(__dirname, '../../.env') });

// Load test species data
const testSpecies = require('./test-species.json');

// API configuration
const XAI_API_KEY = process.env.XAI_API_KEY;
const XAI_RESPONSES_URL = 'https://api.x.ai/v1/responses';

// Model variants to test
const MODELS = {
  reasoning: 'grok-4-1-fast-reasoning',
  nonReasoning: 'grok-4-1-fast-non-reasoning'
};

// All 25 research fields
const ALL_FIELDS = [
  // Identity (1)
  'popular_common_name_ai',
  // Ecological + General (8)
  'habitat_ai', 'elevation_ranges_ai', 'ecological_function_ai', 'native_adapted_habitats_ai',
  'agroforestry_use_cases_ai', 'conservation_status_ai', 'general_description_ai', 'compatible_soil_types_ai',
  // Morphological (10)
  'growth_form_ai', 'leaf_type_ai', 'deciduous_evergreen_ai', 'flower_color_ai',
  'fruit_type_ai', 'bark_characteristics_ai', 'maximum_height_ai', 'maximum_diameter_ai',
  'lifespan_ai', 'maximum_tree_age_ai',
  // Stewardship (6)
  'stewardship_best_practices_ai', 'planting_recipes_ai', 'pruning_maintenance_ai',
  'disease_pest_management_ai', 'fire_management_ai', 'cultural_significance_ai'
];

// =============================================================================
// PROMPTS
// =============================================================================

/**
 * Single comprehensive prompt for all 25 fields
 */
function getSingleCallPrompt(scientificName, commonNames) {
  return `You are a botanical research expert. Research the tree species "${scientificName}" (commonly known as: ${commonNames}) and provide comprehensive data for ALL of the following fields.

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
 * 3-Group Strategy Prompts
 */
function getEcologicalPrompt(scientificName, commonNames) {
  return `Research "${scientificName}" (${commonNames}) - ECOLOGICAL & GENERAL DATA.

Search extensively for these 9 fields:
- popular_common_name_ai: The single most widely-used common name in English (just one name)
- habitat_ai: Natural habitat and ecosystem types
- elevation_ranges_ai: Elevation range in meters (e.g., "100-1500")
- ecological_function_ai: Ecological roles in ecosystem
- native_adapted_habitats_ai: Native range and adapted habitats
- agroforestry_use_cases_ai: Agroforestry applications
- conservation_status_ai: IUCN conservation status
- general_description_ai: Botanical description
- compatible_soil_types_ai: Soil preferences and pH

Return ONLY valid JSON with these exact field names. Use "Data not available" only as last resort.`;
}

function getMorphologicalPrompt(scientificName, commonNames) {
  return `Research "${scientificName}" (${commonNames}) - MORPHOLOGICAL DATA.

Search extensively for these 10 fields:
- growth_form_ai: Growth form and structure
- leaf_type_ai: Leaf characteristics
- deciduous_evergreen_ai: "deciduous", "evergreen", or "semi-deciduous"
- flower_color_ai: Flower colors
- fruit_type_ai: Fruit type and characteristics
- bark_characteristics_ai: Bark appearance
- maximum_height_ai: Maximum height in meters (NUMBER ONLY)
- maximum_diameter_ai: Maximum trunk diameter in meters (NUMBER ONLY)
- lifespan_ai: Typical lifespan
- maximum_tree_age_ai: Maximum age in years (INTEGER ONLY)

Return ONLY valid JSON. For numeric fields, return just the number without units.`;
}

function getStewardshipPrompt(scientificName, commonNames) {
  return `Research "${scientificName}" (${commonNames}) - STEWARDSHIP DATA.

Search extensively for these 6 fields:
- stewardship_best_practices_ai: Cultivation practices
- planting_recipes_ai: Planting requirements
- pruning_maintenance_ai: Pruning practices
- disease_pest_management_ai: Disease/pest management
- fire_management_ai: Fire tolerance and management
- cultural_significance_ai: Cultural significance

Return ONLY valid JSON with these exact field names.`;
}

// =============================================================================
// API CALLS
// =============================================================================

/**
 * Call xAI Responses API with agentic web_search
 */
async function callAgenticAPI(prompt, model) {
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${XAI_API_KEY}`
  };

  const payload = {
    model: model,
    input: prompt,
    tools: [
      { type: 'web_search' }
    ]
  };

  const startTime = Date.now();

  try {
    const response = await axios.post(XAI_RESPONSES_URL, payload, {
      headers,
      timeout: 120000 // 2 minute timeout
    });

    const duration = Date.now() - startTime;

    if (response.data) {
      // Extract the output text from the response
      let outputText = '';

      // xAI Responses API has a 'text' field with the final output
      if (response.data.text) {
        if (typeof response.data.text === 'string') {
          outputText = response.data.text;
        } else if (response.data.text.content) {
          outputText = response.data.text.content;
        }
      }

      // Check output array for message type with output_text content
      if (!outputText && response.data.output && Array.isArray(response.data.output)) {
        for (const item of response.data.output) {
          if (item.type === 'message' && item.content) {
            if (typeof item.content === 'string') {
              outputText += item.content;
            } else if (Array.isArray(item.content)) {
              for (const block of item.content) {
                // Handle output_text type (xAI Responses API format)
                if (block.type === 'output_text' && block.text) {
                  outputText += block.text;
                } else if (block.type === 'text' && block.text) {
                  outputText += block.text;
                } else if (typeof block === 'string') {
                  outputText += block;
                }
              }
            }
          }
        }
      }

      // Fallback to chat completions format
      if (!outputText && response.data.choices) {
        outputText = response.data.choices[0]?.message?.content || '';
      }

      console.log('  Extracted response length:', outputText.length, 'chars');

      // Extract JSON from the response
      const jsonMatch = outputText.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        try {
          const parsedData = JSON.parse(jsonMatch[0]);
          return {
            success: true,
            data: parsedData,
            raw_response: outputText,
            usage: response.data.usage,
            duration_ms: duration,
            citations: response.data.citations || []
          };
        } catch (parseError) {
          console.error('  JSON parsing error:', parseError.message);
          return {
            success: false,
            error: 'JSON parsing failed',
            raw_response: outputText,
            duration_ms: duration
          };
        }
      }

      return {
        success: false,
        error: 'No JSON found in response',
        raw_response: outputText,
        duration_ms: duration
      };
    }

    return {
      success: false,
      error: 'Empty response from API',
      duration_ms: duration
    };

  } catch (error) {
    const duration = Date.now() - startTime;
    console.error('  API Error:', error.response?.data || error.message);
    return {
      success: false,
      error: error.response?.data?.error?.message || error.message,
      duration_ms: duration
    };
  }
}

// =============================================================================
// RESEARCH STRATEGIES
// =============================================================================

/**
 * Single-call strategy: One comprehensive request for all 24 fields
 */
async function researchSingleCall(scientificName, commonNames, model) {
  console.log(`\n📡 Single-call strategy with ${model}...`);

  const prompt = getSingleCallPrompt(scientificName, commonNames);
  const result = await callAgenticAPI(prompt, model);

  if (result.success) {
    // Ensure all fields exist
    ALL_FIELDS.forEach(field => {
      if (!(field in result.data)) {
        result.data[field] = null;
      }
    });

    // Convert numeric fields
    result.data = normalizeNumericFields(result.data);
  }

  return {
    strategy: 'single_call',
    model: model,
    api_calls: 1,
    ...result
  };
}

/**
 * 3-group parallel strategy: Three focused requests
 */
async function researchThreeGroup(scientificName, commonNames, model) {
  console.log(`\n📡 3-group parallel strategy with ${model}...`);

  const prompts = {
    ecological: getEcologicalPrompt(scientificName, commonNames),
    morphological: getMorphologicalPrompt(scientificName, commonNames),
    stewardship: getStewardshipPrompt(scientificName, commonNames)
  };

  // Run all three in parallel
  const [ecological, morphological, stewardship] = await Promise.all([
    callAgenticAPI(prompts.ecological, model),
    callAgenticAPI(prompts.morphological, model),
    callAgenticAPI(prompts.stewardship, model)
  ]);

  // Combine results
  const combinedData = {
    ...(ecological.data || {}),
    ...(morphological.data || {}),
    ...(stewardship.data || {})
  };

  // Ensure all fields exist
  ALL_FIELDS.forEach(field => {
    if (!(field in combinedData)) {
      combinedData[field] = null;
    }
  });

  // Calculate totals
  const totalDuration = (ecological.duration_ms || 0) +
                        (morphological.duration_ms || 0) +
                        (stewardship.duration_ms || 0);

  const totalTokens = (ecological.usage?.total_tokens || 0) +
                      (morphological.usage?.total_tokens || 0) +
                      (stewardship.usage?.total_tokens || 0);

  const allSuccess = ecological.success && morphological.success && stewardship.success;

  return {
    strategy: 'three_group',
    model: model,
    api_calls: 3,
    success: allSuccess,
    data: normalizeNumericFields(combinedData),
    duration_ms: totalDuration,
    usage: { total_tokens: totalTokens },
    group_results: {
      ecological: { success: ecological.success, fields: Object.keys(ecological.data || {}).length },
      morphological: { success: morphological.success, fields: Object.keys(morphological.data || {}).length },
      stewardship: { success: stewardship.success, fields: Object.keys(stewardship.data || {}).length }
    },
    raw_responses: {
      ecological: ecological.raw_response,
      morphological: morphological.raw_response,
      stewardship: stewardship.raw_response
    }
  };
}

/**
 * Normalize numeric fields to proper types
 */
function normalizeNumericFields(data) {
  if (data.maximum_height_ai && typeof data.maximum_height_ai === 'string') {
    const height = parseFloat(data.maximum_height_ai);
    data.maximum_height_ai = isNaN(height) ? null : height;
  }
  if (data.maximum_diameter_ai && typeof data.maximum_diameter_ai === 'string') {
    const diameter = parseFloat(data.maximum_diameter_ai);
    data.maximum_diameter_ai = isNaN(diameter) ? null : diameter;
  }
  if (data.maximum_tree_age_ai && typeof data.maximum_tree_age_ai === 'string') {
    const age = parseInt(data.maximum_tree_age_ai);
    data.maximum_tree_age_ai = isNaN(age) ? null : age;
  }
  return data;
}

// =============================================================================
// ANALYSIS & REPORTING
// =============================================================================

/**
 * Calculate field completion stats
 */
function analyzeCompletion(data) {
  let filled = 0;
  let empty = 0;
  const fieldStatus = {};

  ALL_FIELDS.forEach(field => {
    const value = data[field];
    const hasData = value &&
                    value !== 'Data not available' &&
                    value !== 'No specific information found' &&
                    value !== null;
    fieldStatus[field] = hasData;
    if (hasData) filled++;
    else empty++;
  });

  return {
    filled,
    total: ALL_FIELDS.length,
    percentage: Math.round((filled / ALL_FIELDS.length) * 100),
    fieldStatus
  };
}

/**
 * Print comparison table
 */
function printComparisonTable(results) {
  console.log('\n' + '='.repeat(80));
  console.log('COMPARISON SUMMARY');
  console.log('='.repeat(80));

  console.log('\n| Strategy | Model | Fields | Duration | Tokens | Success |');
  console.log('|----------|-------|--------|----------|--------|---------|');

  results.forEach(r => {
    const completion = analyzeCompletion(r.data || {});
    const modelShort = r.model.includes('non-reasoning') ? 'non-reason' : 'reasoning';
    const stratShort = r.strategy === 'single_call' ? 'Single' : '3-Group';
    console.log(`| ${stratShort.padEnd(8)} | ${modelShort.padEnd(10)} | ${completion.filled}/${completion.total} (${completion.percentage}%) | ${(r.duration_ms/1000).toFixed(1)}s | ${(r.usage?.total_tokens || 0).toLocaleString().padStart(7)} | ${r.success ? '✓' : '✗'} |`);
  });
}

// =============================================================================
// MAIN TEST RUNNER
// =============================================================================

/**
 * Run full comparison test for a species
 */
async function runComparisonTest(scientificName, commonNames, taxonId = null) {
  console.log('\n' + '='.repeat(80));
  console.log(`🌳 GROK 4.1 AGENTIC API COMPARISON TEST`);
  console.log('='.repeat(80));
  console.log(`Species: ${scientificName}`);
  console.log(`Common names: ${commonNames}`);
  if (taxonId) console.log(`Taxon ID: ${taxonId}`);
  console.log(`Timestamp: ${new Date().toISOString()}`);

  const allResults = [];

  // Test each combination
  const testConfigs = [
    { strategy: 'single', model: MODELS.reasoning, name: 'Single + Reasoning' },
    { strategy: 'single', model: MODELS.nonReasoning, name: 'Single + Non-Reasoning' },
    { strategy: 'threeGroup', model: MODELS.reasoning, name: '3-Group + Reasoning' },
    { strategy: 'threeGroup', model: MODELS.nonReasoning, name: '3-Group + Non-Reasoning' }
  ];

  for (const config of testConfigs) {
    console.log(`\n${'─'.repeat(60)}`);
    console.log(`Testing: ${config.name}`);

    let result;
    if (config.strategy === 'single') {
      result = await researchSingleCall(scientificName, commonNames, config.model);
    } else {
      result = await researchThreeGroup(scientificName, commonNames, config.model);
    }

    const completion = analyzeCompletion(result.data || {});
    console.log(`  Result: ${result.success ? '✓ Success' : '✗ Failed'}`);
    console.log(`  Fields: ${completion.filled}/${completion.total} (${completion.percentage}%)`);
    console.log(`  Duration: ${(result.duration_ms/1000).toFixed(1)}s`);

    allResults.push(result);
  }

  // Print comparison
  printComparisonTable(allResults);

  // Save results
  const outputDir = path.join(__dirname, 'test-results', 'grok-agentic');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const filename = `${scientificName.replace(/ /g, '_')}_comparison_${Date.now()}.json`;
  const filepath = path.join(outputDir, filename);

  const fullResults = {
    metadata: {
      species_scientific_name: scientificName,
      common_names: commonNames,
      taxon_id: taxonId,
      timestamp: new Date().toISOString(),
      test_type: 'agentic_comparison'
    },
    results: allResults.map(r => ({
      strategy: r.strategy,
      model: r.model,
      success: r.success,
      api_calls: r.api_calls,
      duration_ms: r.duration_ms,
      usage: r.usage,
      completion: analyzeCompletion(r.data || {}),
      data: r.data,
      group_results: r.group_results,
      raw_responses: r.raw_responses
    }))
  };

  fs.writeFileSync(filepath, JSON.stringify(fullResults, null, 2));
  console.log(`\n✅ Results saved to: ${filename}`);

  return fullResults;
}

/**
 * Run single test (one strategy, one model)
 */
async function runSingleTest(scientificName, commonNames, strategy, model, taxonId = null) {
  console.log(`\n🌳 Testing: ${scientificName}`);
  console.log(`   Strategy: ${strategy}, Model: ${model}`);

  let result;
  if (strategy === 'single') {
    result = await researchSingleCall(scientificName, commonNames, model);
  } else {
    result = await researchThreeGroup(scientificName, commonNames, model);
  }

  const completion = analyzeCompletion(result.data || {});

  console.log(`\n📊 Results:`);
  console.log(`   Success: ${result.success ? '✓' : '✗'}`);
  console.log(`   Fields: ${completion.filled}/${completion.total} (${completion.percentage}%)`);
  console.log(`   Duration: ${(result.duration_ms/1000).toFixed(1)}s`);

  // Show field breakdown
  console.log(`\n   Field breakdown:`);
  ALL_FIELDS.forEach(field => {
    const hasData = completion.fieldStatus[field];
    console.log(`   ${hasData ? '✓' : '✗'} ${field}`);
  });

  // Save result
  const outputDir = path.join(__dirname, 'test-results', 'grok-agentic');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const modelShort = model.includes('reasoning') ? 'reasoning' : 'nonreasoning';
  const filename = `${scientificName.replace(/ /g, '_')}_${strategy}_${modelShort}_${Date.now()}.json`;
  const filepath = path.join(outputDir, filename);

  const output = {
    metadata: {
      species_scientific_name: scientificName,
      common_names: commonNames,
      taxon_id: taxonId,
      timestamp: new Date().toISOString(),
      strategy,
      model
    },
    ...result,
    completion
  };

  fs.writeFileSync(filepath, JSON.stringify(output, null, 2));
  console.log(`\n✅ Saved to: ${filename}`);

  return output;
}

// =============================================================================
// CLI
// =============================================================================

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    console.log(`
Grok 4.1 Fast Agentic API Testing
=================================

Tests the new xAI Responses API with agentic web_search for tree research.

Usage:
  node test-grok-agentic.js --compare --species <taxon_id>     # Full comparison test
  node test-grok-agentic.js --compare --custom "<name>" "<common>"

  node test-grok-agentic.js --single --reasoning --species <taxon_id>
  node test-grok-agentic.js --3group --non-reasoning --custom "<name>" "<common>"

  node test-grok-agentic.js --list                             # List test species

Options:
  --compare         Run all 4 combinations (2 strategies × 2 models)
  --single          Use single-call strategy
  --3group          Use 3-group parallel strategy
  --reasoning       Use grok-4-1-fast-reasoning model
  --non-reasoning   Use grok-4-1-fast-non-reasoning model
  --species <id>    Use species from test-species.json
  --custom          Provide custom species name and common names
  --list            List available test species

Examples:
  # Full comparison on Ginkgo biloba
  node test-grok-agentic.js --compare --species AngGiGiGN21141-00

  # Single test with specific config
  node test-grok-agentic.js --single --reasoning --custom "Quercus robur" "English oak"
`);
    return;
  }

  // Check API key
  if (!XAI_API_KEY) {
    console.error('❌ XAI_API_KEY not found in .env file');
    return;
  }

  // List species
  if (args.includes('--list')) {
    console.log('\n📋 Available test species:');
    testSpecies.forEach(s => {
      console.log(`\n  ${s.taxon_id}`);
      console.log(`  Scientific: ${s.species_scientific_name}`);
      console.log(`  Common: ${s.common_name}`);
    });
    return;
  }

  // Parse species
  let scientificName, commonNames, taxonId;

  if (args.includes('--species')) {
    const idx = args.indexOf('--species') + 1;
    taxonId = args[idx];
    const species = testSpecies.find(s => s.taxon_id === taxonId);
    if (!species) {
      console.error(`❌ Species "${taxonId}" not found. Use --list to see available.`);
      return;
    }
    scientificName = species.species_scientific_name;
    commonNames = species.common_name;
  } else if (args.includes('--custom')) {
    const idx = args.indexOf('--custom') + 1;
    scientificName = args[idx];
    commonNames = args[idx + 1];
    if (!scientificName || !commonNames) {
      console.error('❌ --custom requires "<scientific_name>" "<common_names>"');
      return;
    }
  } else {
    console.error('❌ Please specify --species or --custom');
    return;
  }

  // Run appropriate test
  if (args.includes('--compare')) {
    await runComparisonTest(scientificName, commonNames, taxonId);
  } else {
    // Single test
    const strategy = args.includes('--3group') ? 'threeGroup' : 'single';
    const model = args.includes('--non-reasoning') ? MODELS.nonReasoning : MODELS.reasoning;
    await runSingleTest(scientificName, commonNames, strategy, model, taxonId);
  }
}

// Run
if (require.main === module) {
  main().catch(error => {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { runComparisonTest, runSingleTest, MODELS };
