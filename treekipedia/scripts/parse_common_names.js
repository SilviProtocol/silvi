#!/usr/bin/env node
/**
 * Bulk parse existing common_name blobs into structured species_common_names rows.
 *
 * Patterns handled:
 * - Semicolon-delimited groups: "Oak; Chêne; Roble"
 * - Comma-delimited names within groups: "Caoba, Mahogany, Mogno"
 * - Parenthetical language markers: "Mlilana (Rufiji)", "Mpira(Zaramo)"
 * - Bracket markers: "Tiama [Commercial]", "Tvulpojikpalg [Moba]"
 * - Leading semicolons (80% of entries): "; Oak; Chêne"
 * - Empty segments: "Mango; ; Mango Criollo"
 * - Cyrillic, Japanese, other scripts
 *
 * Also populates species.display_common_name using priority:
 *   1. popular_common_name_ai (if exists)
 *   2. First non-empty, non-parenthetical name from common_name
 *   3. NULL
 *
 * Usage: node scripts/parse_common_names.js [--dry-run] [--limit N]
 */

const { Pool } = require('pg');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config({ path: path.join(__dirname, '../.env') });

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

const DRY_RUN = process.argv.includes('--dry-run');
const LIMIT_ARG = process.argv.indexOf('--limit');
const LIMIT = LIMIT_ARG !== -1 ? parseInt(process.argv[LIMIT_ARG + 1]) : null;
const BATCH_SIZE = 500;

// Script detection patterns
const CYRILLIC_RE = /[\u0400-\u04FF]/;
const CJK_RE = /[\u3000-\u9FFF\uF900-\uFAFF]/;
const ARABIC_RE = /[\u0600-\u06FF]/;
const DEVANAGARI_RE = /[\u0900-\u097F]/;
const THAI_RE = /[\u0E00-\u0E7F]/;

// Common language marker mappings (parenthetical or bracket content → ISO 639-1)
const LANG_MARKERS = {
  // Direct language names
  'english': 'en', 'french': 'fr', 'spanish': 'es', 'portuguese': 'pt',
  'german': 'de', 'italian': 'it', 'dutch': 'nl', 'russian': 'ru',
  'japanese': 'ja', 'chinese': 'zh', 'arabic': 'ar', 'hindi': 'hi',
  'swahili': 'sw', 'malay': 'ms', 'indonesian': 'id', 'thai': 'th',
  'vietnamese': 'vi', 'korean': 'ko', 'turkish': 'tr', 'persian': 'fa',
  'polish': 'pl', 'czech': 'cs', 'hungarian': 'hu', 'romanian': 'ro',
  'greek': 'el', 'hebrew': 'he', 'swedish': 'sv', 'norwegian': 'no',
  'danish': 'da', 'finnish': 'fi',
  // African languages / ethnic groups commonly seen in data
  'yoruba': 'yo', 'igbo': 'ig', 'hausa': 'ha', 'zulu': 'zu',
  'kikuyu': 'ki', 'amharic': 'am',
  // Indigenous language markers (map to region instead)
  'maya': null, 'nahuatl': null, 'náhuatl': null, 'huasteco': null,
  'zapoteco': null, 'mixteco': null, 'totonaco': null,
};

// African ethnic/regional language markers → treat as language_code = null, note as context
const AFRICAN_REGIONAL = new Set([
  'sambaa', 'kisambaa', 'kishambaa', 'kishangaa', 'hehe', 'gogo',
  'mwera', 'kiroba', 'rangi', 'zigua', 'sumbwe', 'masai', 'digo',
  'rufiji', 'zaramo', 'fang', 'edo', 'n.p.'
]);

/**
 * Detect language from script used in name
 */
function detectScriptLanguage(name) {
  if (CYRILLIC_RE.test(name)) return 'ru'; // Most Cyrillic in this dataset is Russian
  if (CJK_RE.test(name)) return 'ja';      // Most CJK in this dataset is Japanese
  if (ARABIC_RE.test(name)) return 'ar';
  if (DEVANAGARI_RE.test(name)) return 'hi';
  if (THAI_RE.test(name)) return 'th';
  return null;
}

/**
 * Extract language/context marker from parentheses or brackets
 * Returns { cleanName, languageCode, markerText }
 */
function extractMarker(rawName) {
  // Match trailing (Marker) or (Marker) patterns
  const parenMatch = rawName.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
  const bracketMatch = rawName.match(/^(.+?)\s*\[([^\]]+)\]\s*$/);

  const match = parenMatch || bracketMatch;
  if (!match) {
    return { cleanName: rawName.trim(), languageCode: null, markerText: null };
  }

  const cleanName = match[1].trim();
  const markerText = match[2].trim();
  const markerLower = markerText.toLowerCase();

  // Check if it's a known language
  if (LANG_MARKERS.hasOwnProperty(markerLower)) {
    return { cleanName, languageCode: LANG_MARKERS[markerLower], markerText };
  }

  // Check if it's an African regional marker
  if (AFRICAN_REGIONAL.has(markerLower)) {
    return { cleanName, languageCode: null, markerText };
  }

  // "Commercial" or other non-language markers — keep in name
  if (['commercial', 'trade', 'general'].includes(markerLower)) {
    return { cleanName: rawName.trim(), languageCode: null, markerText: null };
  }

  // Unknown marker — could be a language/dialect we don't map. Strip it but no lang code
  return { cleanName, languageCode: null, markerText };
}

/**
 * Parse a single common_name blob into structured name entries
 */
function parseCommonNameBlob(commonName, taxonId) {
  if (!commonName || commonName.trim() === '') return [];

  const entries = [];
  const seen = new Set(); // dedup: name|lang

  // Split by semicolons
  const segments = commonName.split(';');

  let position = 0;
  for (const segment of segments) {
    const trimmed = segment.trim();
    if (!trimmed || trimmed === 'NA' || trimmed === 'na') continue;

    // Split by commas within segment
    const names = trimmed.split(',');

    for (const rawName of names) {
      const name = rawName.trim();
      if (!name || name === 'NA' || name === 'na' || name.length < 2) continue;

      // Extract any language marker
      const { cleanName, languageCode: markerLang } = extractMarker(name);
      if (!cleanName || cleanName.length < 2) continue;

      // Detect script-based language
      const scriptLang = detectScriptLanguage(cleanName);
      const languageCode = markerLang || scriptLang || null;

      // Dedup key
      const dedupKey = `${cleanName.toLowerCase()}|${languageCode || ''}`;
      if (seen.has(dedupKey)) continue;
      seen.add(dedupKey);

      entries.push({
        taxon_id: taxonId,
        name: cleanName,
        language_code: languageCode,
        position: position,
        source: 'bulk_import',
      });
      position++;
    }
  }

  return entries;
}

/**
 * Choose the best display name for a species
 */
function chooseDisplayName(popularNameAi, commonName) {
  // Priority 1: AI-researched name
  if (popularNameAi && popularNameAi.trim()) {
    return popularNameAi.trim();
  }

  // Priority 2: First clean name from common_name blob
  if (!commonName || commonName.trim() === '') return null;

  const segments = commonName.split(';');
  for (const segment of segments) {
    const trimmed = segment.trim();
    if (!trimmed || trimmed === 'NA') continue;

    // Take first comma-separated name from this segment
    const names = trimmed.split(',');
    for (const rawName of names) {
      const name = rawName.trim();
      if (!name || name === 'NA' || name.length < 2) continue;

      const { cleanName } = extractMarker(name);
      if (cleanName && cleanName.length >= 2) {
        // Prefer names that look English (Latin script, no complex diacritics)
        if (!CYRILLIC_RE.test(cleanName) && !CJK_RE.test(cleanName) &&
            !ARABIC_RE.test(cleanName) && !THAI_RE.test(cleanName)) {
          return cleanName;
        }
      }
    }
  }

  // Fallback: return any first clean name
  for (const segment of commonName.split(';')) {
    const trimmed = segment.trim();
    if (!trimmed || trimmed === 'NA') continue;
    const { cleanName } = extractMarker(trimmed.split(',')[0].trim());
    if (cleanName && cleanName.length >= 2) return cleanName;
  }

  return null;
}

async function main() {
  const client = await pool.connect();

  try {
    console.log(`Starting common name parsing${DRY_RUN ? ' (DRY RUN)' : ''}...`);

    // Fetch species with common names
    const limitClause = LIMIT ? `LIMIT ${LIMIT}` : '';
    const { rows: species } = await client.query(`
      SELECT taxon_id, common_name, popular_common_name_ai
      FROM species
      WHERE common_name IS NOT NULL AND common_name != ''
      ORDER BY taxon_id
      ${limitClause}
    `);

    console.log(`Found ${species.length} species with common names`);

    let totalNames = 0;
    let totalSpecies = 0;
    let displayNamesSet = 0;
    let allEntries = [];
    let displayUpdates = [];

    for (const sp of species) {
      const entries = parseCommonNameBlob(sp.common_name, sp.taxon_id);
      if (entries.length > 0) {
        // Mark first entry for each language as primary
        const seenLangs = new Set();
        for (const entry of entries) {
          const langKey = entry.language_code || '__null__';
          if (!seenLangs.has(langKey)) {
            entry.is_primary = true;
            seenLangs.add(langKey);
          } else {
            entry.is_primary = false;
          }
        }

        allEntries.push(...entries);
        totalSpecies++;
        totalNames += entries.length;
      }

      // Compute display name
      const displayName = chooseDisplayName(sp.popular_common_name_ai, sp.common_name);
      if (displayName) {
        displayUpdates.push({ taxon_id: sp.taxon_id, display_common_name: displayName });
        displayNamesSet++;
      }
    }

    console.log(`Parsed ${totalNames} names from ${totalSpecies} species`);
    console.log(`Display names computed for ${displayNamesSet} species`);

    if (DRY_RUN) {
      // Show sample
      console.log('\n--- Sample parsed names (first 30) ---');
      for (const entry of allEntries.slice(0, 30)) {
        const lang = entry.language_code || '??';
        const primary = entry.is_primary ? '*' : ' ';
        console.log(`  ${primary} [${lang}] ${entry.name} (${entry.taxon_id})`);
      }
      console.log('\n--- Sample display names (first 20) ---');
      for (const upd of displayUpdates.slice(0, 20)) {
        console.log(`  ${upd.taxon_id}: "${upd.display_common_name}"`);
      }
      console.log(`\nDry run complete. Would insert ${totalNames} rows and update ${displayNamesSet} display names.`);
      return;
    }

    // Insert in batches
    await client.query('BEGIN');

    console.log(`\nInserting ${totalNames} common name rows in batches of ${BATCH_SIZE}...`);
    let inserted = 0;

    for (let i = 0; i < allEntries.length; i += BATCH_SIZE) {
      const batch = allEntries.slice(i, i + BATCH_SIZE);

      // Build bulk INSERT with ON CONFLICT skip
      const values = [];
      const params = [];
      let paramIdx = 1;

      for (const entry of batch) {
        values.push(`($${paramIdx}, $${paramIdx + 1}, $${paramIdx + 2}, $${paramIdx + 3}, $${paramIdx + 4})`);
        params.push(entry.taxon_id, entry.name, entry.language_code, entry.source, entry.is_primary);
        paramIdx += 5;
      }

      const sql = `
        INSERT INTO species_common_names (taxon_id, name, language_code, source, is_primary)
        VALUES ${values.join(', ')}
        ON CONFLICT (taxon_id, name, language_code) DO NOTHING
      `;

      const result = await client.query(sql, params);
      inserted += result.rowCount;

      if ((i / BATCH_SIZE) % 20 === 0) {
        const pct = Math.round((i / allEntries.length) * 100);
        console.log(`  ${pct}% — ${inserted} rows inserted so far...`);
      }
    }

    console.log(`Inserted ${inserted} common name rows (${totalNames - inserted} duplicates skipped)`);

    // Update display names in batches
    console.log(`\nUpdating display_common_name for ${displayUpdates.length} species...`);
    let displayUpdated = 0;

    for (let i = 0; i < displayUpdates.length; i += BATCH_SIZE) {
      const batch = displayUpdates.slice(i, i + BATCH_SIZE);

      // Use a CTE with VALUES for batch update
      const values = [];
      const params = [];
      let paramIdx = 1;

      for (const upd of batch) {
        values.push(`($${paramIdx}, $${paramIdx + 1})`);
        params.push(upd.taxon_id, upd.display_common_name);
        paramIdx += 2;
      }

      const sql = `
        UPDATE species SET display_common_name = v.display_name
        FROM (VALUES ${values.join(', ')}) AS v(tid, display_name)
        WHERE species.taxon_id = v.tid
      `;

      const result = await client.query(sql, params);
      displayUpdated += result.rowCount;
    }

    console.log(`Updated ${displayUpdated} species with display_common_name`);

    await client.query('COMMIT');
    console.log('\nDone!');

  } catch (error) {
    await client.query('ROLLBACK');
    console.error('Error:', error);
    throw error;
  } finally {
    client.release();
    await pool.end();
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
