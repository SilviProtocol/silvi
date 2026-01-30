/**
 * Guide Synthesis Service
 * Uses Grok 4.1 Fast to generate ecoregion reforestation guide content.
 */

const axios = require('axios');

const XAI_API_KEY = process.env.XAI_API_KEY;
const XAI_RESPONSES_URL = 'https://api.x.ai/v1/responses';
const MODEL = 'grok-4-1-fast-reasoning';

/**
 * Map countries to their primary languages for region-specific naming
 */
const COUNTRY_LANGUAGES = {
  // Europe
  'Italy': ['Italian'],
  'Spain': ['Spanish'],
  'Portugal': ['Portuguese'],
  'France': ['French'],
  'Germany': ['German'],
  'Greece': ['Greek'],
  'Croatia': ['Croatian'],
  'Slovenia': ['Slovenian'],
  'Albania': ['Albanian'],
  'Montenegro': ['Montenegrin'],
  'Turkey': ['Turkish'],
  'United Kingdom': ['English'],
  'Ireland': ['English', 'Irish'],
  'Netherlands': ['Dutch'],
  'Belgium': ['Dutch', 'French'],
  'Switzerland': ['German', 'French', 'Italian'],
  'Austria': ['German'],
  'Poland': ['Polish'],
  'Czech Republic': ['Czech'],
  'Romania': ['Romanian'],
  'Bulgaria': ['Bulgarian'],
  'Hungary': ['Hungarian'],
  'Sweden': ['Swedish'],
  'Norway': ['Norwegian'],
  'Finland': ['Finnish', 'Swedish'],
  'Denmark': ['Danish'],
  'Serbia': ['Serbian'],
  'Bosnia and Herzegovina': ['Bosnian', 'Croatian', 'Serbian'],
  'North Macedonia': ['Macedonian'],

  // Americas
  'United States': ['English', 'Spanish'],
  'Canada': ['English', 'French'],
  'Mexico': ['Spanish'],
  'Brazil': ['Portuguese'],
  'Argentina': ['Spanish'],
  'Chile': ['Spanish'],
  'Colombia': ['Spanish'],
  'Peru': ['Spanish', 'Quechua'],
  'Ecuador': ['Spanish'],
  'Bolivia': ['Spanish', 'Quechua', 'Aymara'],
  'Venezuela': ['Spanish'],
  'Costa Rica': ['Spanish'],
  'Panama': ['Spanish'],
  'Guatemala': ['Spanish'],
  'Honduras': ['Spanish'],
  'Nicaragua': ['Spanish'],
  'El Salvador': ['Spanish'],
  'Cuba': ['Spanish'],
  'Dominican Republic': ['Spanish'],
  'Puerto Rico': ['Spanish', 'English'],
  'Jamaica': ['English'],
  'Haiti': ['French', 'Haitian Creole'],
  'Paraguay': ['Spanish', 'Guaraní'],
  'Uruguay': ['Spanish'],

  // Asia
  'China': ['Chinese (Mandarin)'],
  'Japan': ['Japanese'],
  'South Korea': ['Korean'],
  'North Korea': ['Korean'],
  'India': ['Hindi', 'English'],
  'Indonesia': ['Indonesian'],
  'Malaysia': ['Malay', 'English'],
  'Thailand': ['Thai'],
  'Vietnam': ['Vietnamese'],
  'Philippines': ['Filipino', 'English'],
  'Myanmar': ['Burmese'],
  'Nepal': ['Nepali'],
  'Pakistan': ['Urdu', 'English'],
  'Bangladesh': ['Bengali'],
  'Sri Lanka': ['Sinhala', 'Tamil'],
  'Cambodia': ['Khmer'],
  'Laos': ['Lao'],
  'Taiwan': ['Chinese (Mandarin)'],
  'Mongolia': ['Mongolian'],

  // Africa
  'South Africa': ['English', 'Afrikaans', 'Zulu', 'Xhosa'],
  'Kenya': ['Swahili', 'English'],
  'Tanzania': ['Swahili', 'English'],
  'Ethiopia': ['Amharic'],
  'Nigeria': ['English', 'Hausa', 'Yoruba', 'Igbo'],
  'Ghana': ['English', 'Akan'],
  'Morocco': ['Arabic', 'French', 'Berber'],
  'Algeria': ['Arabic', 'French', 'Berber'],
  'Tunisia': ['Arabic', 'French'],
  'Egypt': ['Arabic'],
  'Madagascar': ['Malagasy', 'French'],
  'Democratic Republic of the Congo': ['French', 'Lingala', 'Swahili'],
  'Cameroon': ['French', 'English'],
  'Ivory Coast': ['French'],
  'Senegal': ['French', 'Wolof'],
  'Uganda': ['English', 'Swahili'],
  'Rwanda': ['Kinyarwanda', 'French', 'English'],
  'Zimbabwe': ['English', 'Shona', 'Ndebele'],
  'Mozambique': ['Portuguese'],
  'Angola': ['Portuguese'],
  'Namibia': ['English', 'Afrikaans', 'German'],
  'Botswana': ['English', 'Tswana'],

  // Oceania
  'Australia': ['English'],
  'New Zealand': ['English', 'Māori'],
  'Papua New Guinea': ['English', 'Tok Pisin'],
  'Fiji': ['English', 'Fijian', 'Hindi'],

  // Middle East
  'Israel': ['Hebrew', 'Arabic'],
  'Iran': ['Persian (Farsi)'],
  'Iraq': ['Arabic', 'Kurdish'],
  'Saudi Arabia': ['Arabic'],
  'United Arab Emirates': ['Arabic'],
  'Jordan': ['Arabic'],
  'Lebanon': ['Arabic', 'French'],
  'Syria': ['Arabic'],
  'Yemen': ['Arabic'],
  'Oman': ['Arabic'],
  'Kuwait': ['Arabic'],
  'Qatar': ['Arabic'],
  'Bahrain': ['Arabic'],

  // Central Asia
  'Kazakhstan': ['Kazakh', 'Russian'],
  'Uzbekistan': ['Uzbek', 'Russian'],
  'Turkmenistan': ['Turkmen', 'Russian'],
  'Kyrgyzstan': ['Kyrgyz', 'Russian'],
  'Tajikistan': ['Tajik', 'Russian'],
  'Afghanistan': ['Pashto', 'Dari'],

  // Russia & Caucasus
  'Russia': ['Russian'],
  'Georgia': ['Georgian'],
  'Armenia': ['Armenian'],
  'Azerbaijan': ['Azerbaijani'],
};

/**
 * Get unique languages for a list of countries (excluding English as it's always included)
 */
function getLocalLanguages(countries) {
  const languages = new Set();
  for (const country of countries) {
    const langs = COUNTRY_LANGUAGES[country] || [];
    for (const lang of langs) {
      if (lang !== 'English') {
        languages.add(lang);
      }
    }
  }
  return Array.from(languages);
}

/**
 * Synthesize guide content for an ecoregion using top species data.
 *
 * @param {object} ecoregion - { eco_name, biome_name, realm, area_km2 }
 * @param {Array} topSpecies - Top 20 species with _ai field summaries
 * @param {Array} countries - Countries that overlap with this ecoregion
 * @returns {object} { overview_intro, planting_strategy, climate_context, conservation_notes }
 */
async function synthesizeGuide(ecoregion, topSpecies, countries = []) {
  if (!XAI_API_KEY) {
    throw new Error('XAI_API_KEY not configured');
  }

  // Get local languages for this ecoregion
  const localLanguages = getLocalLanguages(countries);
  const hasLocalLanguages = localLanguages.length > 0;

  // Build naming instruction based on region
  let namingInstruction = '';
  if (hasLocalLanguages) {
    const langList = localLanguages.slice(0, 3).join(', ');
    namingInstruction = `
NAMING CONVENTION:
When referring to species, use both the English common name and the local name where appropriate.
This ecoregion spans: ${countries.slice(0, 5).join(', ')}${countries.length > 5 ? ` and ${countries.length - 5} more countries` : ''}
Local languages: ${langList}
Format: "English Name (Local Name)" - e.g., "Holm Oak (Encina)" for Spanish regions, "Common Myrtle (Mirto)" for Italian regions.
Only include local names for the most prominent species mentions, not every occurrence.`;
  }

  const speciesSummaries = topSpecies.slice(0, 20).map((s, i) => {
    const parts = [`${i + 1}. ${s.scientific_name || s.taxon_id}`];

    // Prefer popular_common_name_ai if available, otherwise include full common_name for LLM to pick from
    if (s.popular_common_name_ai && s.popular_common_name_ai !== 'NA') {
      parts.push(`(${s.popular_common_name_ai})`);
      // Also include other names for regional selection
      if (s.common_name && hasLocalLanguages) {
        const otherNames = s.common_name.length > 150
          ? s.common_name.substring(0, 150) + '...'
          : s.common_name;
        parts.push(`[Other names: ${otherNames}]`);
      }
    } else if (s.common_name) {
      const truncatedNames = s.common_name.length > 200
        ? s.common_name.substring(0, 200) + '...'
        : s.common_name;
      parts.push(`(Common names: ${truncatedNames})`);
    }

    if (s.tier) parts.push(`[${s.tier}]`);
    if (s.general_description_ai && s.general_description_ai !== 'NA') {
      parts.push(`- ${s.general_description_ai.substring(0, 150)}`);
    }
    if (s.habitat_ai && s.habitat_ai !== 'NA') {
      parts.push(`Habitat: ${s.habitat_ai.substring(0, 100)}`);
    }
    if (s.ecological_function_ai && s.ecological_function_ai !== 'NA') {
      parts.push(`Ecology: ${s.ecological_function_ai.substring(0, 100)}`);
    }
    if (s.maximum_height_ai && s.maximum_height_ai !== 'NA') {
      parts.push(`Height: ${s.maximum_height_ai}m`);
    }
    if (s.is_native) parts.push('[NATIVE]');
    return parts.join(' ');
  }).join('\n');

  const prompt = `You are an expert reforestation ecologist. Generate a reforestation guide for the following ecoregion.

ECOREGION:
- Name: ${ecoregion.eco_name}
- Biome: ${ecoregion.biome_name}
- Realm: ${ecoregion.realm}
- Area: ${Math.round(ecoregion.area_km2).toLocaleString()} km²
- Countries: ${countries.slice(0, 10).join(', ')}${countries.length > 10 ? ` (+${countries.length - 10} more)` : ''}
${namingInstruction}

TOP RECOMMENDED SPECIES (ranked by LEAF ecological aptness score):
${speciesSummaries}

Return a JSON object with exactly these 4 keys:
{
  "overview_intro": "2-3 paragraph introduction to this ecoregion's ecology, biodiversity significance, and reforestation potential. Reference specific species from the list by name.",
  "planting_strategy": "2-3 paragraphs on recommended planting approach: species mix ratios, canopy layering, successional planting stages, spacing, and site preparation specific to this biome.",
  "climate_context": "1-2 paragraphs on climate conditions, seasonal patterns, rainfall, temperature ranges, and how they affect tree establishment in this ecoregion.",
  "conservation_notes": "1-2 paragraphs on conservation priorities, any threatened species in the list, habitat connectivity, and alignment with regional conservation goals."
}

RULES:
1. Be specific to this ecoregion — avoid generic reforestation advice
2. Reference actual species from the list by their common names (use local names where appropriate per the naming convention above)
3. Return ONLY valid JSON, no markdown or additional text
4. Each section should be substantive prose (not bullet points)
5. When a species has multiple common names, choose the most recognizable one for the region`;

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${XAI_API_KEY}`
  };

  const body = {
    model: MODEL,
    tools: [{ type: 'web_search' }],
    input: prompt,
    temperature: 0.4
  };

  try {
    console.log(`[GuideSynthesis] Synthesizing guide for ${ecoregion.eco_name}`);
    console.log(`[GuideSynthesis] Countries: ${countries.length}, Local languages: ${localLanguages.join(', ') || 'none'}`);

    const response = await axios.post(XAI_RESPONSES_URL, body, {
      headers,
      timeout: 120000
    });

    // Extract text from response
    let text = '';
    if (response.data?.output) {
      for (const block of response.data.output) {
        if (block.type === 'message' && block.content) {
          for (const part of block.content) {
            if (part.type === 'output_text') {
              text += part.text;
            }
          }
        }
      }
    }

    if (!text) {
      throw new Error('Empty response from Grok');
    }

    // Clean and parse JSON
    let cleaned = text.trim();
    if (cleaned.startsWith('```')) {
      cleaned = cleaned.replace(/^```(?:json)?\n?/, '').replace(/\n?```$/, '');
    }

    const result = JSON.parse(cleaned);

    // Validate required keys
    const required = ['overview_intro', 'planting_strategy', 'climate_context', 'conservation_notes'];
    for (const key of required) {
      if (!result[key] || typeof result[key] !== 'string') {
        result[key] = null;
      }
    }

    console.log(`[GuideSynthesis] Successfully synthesized guide for ${ecoregion.eco_name}`);
    return result;
  } catch (error) {
    console.error('Guide synthesis error:', error.message);
    throw error;
  }
}

module.exports = { synthesizeGuide, getLocalLanguages };
