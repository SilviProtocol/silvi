/**
 * WCVP (World Checklist of Vascular Plants) Region Mappings
 *
 * WCVP uses geographic regions that don't always match country names.
 * This module provides mappings from Natural Earth country names to WCVP regions.
 */

// US States used in WCVP
const US_STATES = [
  'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
  'Connecticut', 'Delaware', 'District of Columbia', 'Florida', 'Georgia',
  'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky',
  'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
  'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire',
  'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota',
  'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode I.', 'South Carolina',
  'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia',
  'Washington', 'West Virginia', 'Wisconsin', 'Wyoming'
];

// Canadian provinces used in WCVP
const CANADIAN_PROVINCES = [
  'Alberta', 'British Columbia', 'Labrador', 'Manitoba', 'New Brunswick',
  'Newfoundland', 'Northwest Territorie', 'Nova Scotia', 'Nunavut',
  'Ontario', 'Prince Edward I.', 'Québec', 'Saskatchewan', 'Yukon'
];

// Brazilian regions used in WCVP
const BRAZILIAN_REGIONS = [
  'Brazil North', 'Brazil Northeast', 'Brazil South', 'Brazil Southeast',
  'Brazil West-Central'
];

// Chinese regions used in WCVP
const CHINESE_REGIONS = [
  'China North-Central', 'China South-Central', 'China Southeast',
  'Hainan', 'Inner Mongolia', 'Manchuria', 'Qinghai', 'Tibet', 'Xinjiang'
];

// Mexican regions used in WCVP
const MEXICAN_REGIONS = [
  'Mexico Central', 'Mexico Gulf', 'Mexico Northeast', 'Mexico Northwest',
  'Mexico Southeast', 'Mexico Southwest'
];

// Argentine regions used in WCVP
const ARGENTINE_REGIONS = [
  'Argentina Northeast', 'Argentina Northwest', 'Argentina South'
];

// Australian states/territories used in WCVP
const AUSTRALIAN_REGIONS = [
  'New South Wales', 'Northern Territory', 'Queensland', 'South Australia',
  'Tasmania', 'Victoria', 'Western Australia'
];

// Chilean regions used in WCVP
const CHILEAN_REGIONS = [
  'Chile Central', 'Chile North', 'Chile South'
];

// Indian regions used in WCVP
const INDIAN_REGIONS = [
  'Assam', 'East Himalaya', 'West Himalaya', 'India', 'Andaman Is.',
  'Nicobar Is.', 'Laccadive Is.'
];

// New Zealand regions used in WCVP
const NEW_ZEALAND_REGIONS = [
  'New Zealand North', 'New Zealand South'
];

// Russian regions used in WCVP
const RUSSIAN_REGIONS = [
  'Altay', 'Amur', 'Buryatiya', 'Central European Rus', 'Chita',
  'East European Russia', 'Irkutsk', 'Kamchatka', 'Khabarovsk',
  'Krasnoyarsk', 'Magadan', 'North Caucasus', 'North European Russi',
  'Northwest European R', 'Primorye', 'Sakhalin', 'South European Russi',
  'Transcaucasus', 'Tuva', 'West Siberia', 'Yakutskiya'
];

// South African provinces used in WCVP
const SOUTH_AFRICAN_REGIONS = [
  'Cape Provinces', 'Free State', 'KwaZulu-Natal', 'Northern Provinces'
];

// Country to WCVP regions mapping
const COUNTRY_TO_WCVP_REGIONS = {
  'United States': US_STATES,
  'United States of America': US_STATES,
  'Canada': CANADIAN_PROVINCES,
  'Brazil': BRAZILIAN_REGIONS,
  'China': CHINESE_REGIONS,
  'Mexico': MEXICAN_REGIONS,
  'Argentina': ARGENTINE_REGIONS,
  'Australia': AUSTRALIAN_REGIONS,
  'Chile': CHILEAN_REGIONS,
  'India': INDIAN_REGIONS,
  'New Zealand': NEW_ZEALAND_REGIONS,
  'Russia': RUSSIAN_REGIONS,
  'Russian Federation': RUSSIAN_REGIONS,
  'South Africa': SOUTH_AFRICAN_REGIONS,
};

/**
 * Get WCVP region patterns for a country name
 * @param {string} countryName - Natural Earth country name
 * @returns {string[]} - Array of WCVP region names to search for
 */
function getWcvpRegionsForCountry(countryName) {
  // Check if we have a specific mapping
  if (COUNTRY_TO_WCVP_REGIONS[countryName]) {
    return COUNTRY_TO_WCVP_REGIONS[countryName];
  }

  // For countries without specific mappings, use the country name directly
  return [countryName];
}

/**
 * Build SQL WHERE clause conditions for wcvp_native matching
 * @param {string[]} countries - Array of country names from ecoregion
 * @param {number} startParamIndex - Starting parameter index for SQL placeholders
 * @returns {{ condition: string, params: string[] }} - SQL condition and parameters
 */
function buildWcvpNativeCondition(countries, startParamIndex = 1) {
  const allRegions = [];

  for (const country of countries) {
    const regions = getWcvpRegionsForCountry(country);
    allRegions.push(...regions);
  }

  if (allRegions.length === 0) {
    return { condition: '', params: [] };
  }

  // Build OR conditions for each region
  const conditions = allRegions.map((_, idx) =>
    `wcvp_native LIKE $${startParamIndex + idx}`
  );

  const params = allRegions.map(region => `%${region}%`);

  return {
    condition: `(${conditions.join(' OR ')})`,
    params
  };
}

/**
 * Build SQL WHERE clause for wcvp_introduced exclusion
 * @param {string[]} countries - Array of country names from ecoregion
 * @param {number} startParamIndex - Starting parameter index
 * @returns {{ condition: string, params: string[] }}
 */
function buildWcvpIntroducedExclusion(countries, startParamIndex = 1) {
  const allRegions = [];

  for (const country of countries) {
    const regions = getWcvpRegionsForCountry(country);
    allRegions.push(...regions);
  }

  if (allRegions.length === 0) {
    return { condition: '', params: [] };
  }

  // Exclude species that are introduced in any of these regions
  const placeholders = allRegions.map((_, idx) =>
    `$${startParamIndex + idx}`
  );

  const params = allRegions.map(region => `%${region}%`);

  return {
    condition: `(wcvp_introduced IS NULL OR wcvp_introduced NOT LIKE ALL(ARRAY[${placeholders.join(', ')}]))`,
    params
  };
}

module.exports = {
  US_STATES,
  CANADIAN_PROVINCES,
  BRAZILIAN_REGIONS,
  CHINESE_REGIONS,
  MEXICAN_REGIONS,
  COUNTRY_TO_WCVP_REGIONS,
  getWcvpRegionsForCountry,
  buildWcvpNativeCondition,
  buildWcvpIntroducedExclusion
};
