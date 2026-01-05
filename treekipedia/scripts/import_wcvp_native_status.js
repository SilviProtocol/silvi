/**
 * Import WCVP Native/Introduced Status from V11 CSV
 *
 * This script adds wcvp_native and wcvp_introduced columns to the species table
 * and populates them from the Treekipedia V11 CSV file.
 *
 * Usage: node scripts/import_wcvp_native_status.js
 */

const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');
const readline = require('readline');

require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const pool = new Pool({
  connectionString: process.env.DATABASE_URL
});

const CSV_FILE = path.join(__dirname, '..', 'Treekipedia_V11_Native_introduced_December_09d.csv');
const BATCH_SIZE = 1000;

// Track statistics
const stats = {
  totalRows: 0,
  updatedSpecies: 0,
  skippedNoData: 0,
  notFoundInDb: 0,
  errors: 0
};

/**
 * Parse a CSV line handling quoted fields with commas
 */
function parseCSVLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());

  return result;
}

/**
 * Add columns if they don't exist
 */
async function ensureColumns() {
  const client = await pool.connect();
  try {
    // Check if columns exist
    const checkResult = await client.query(`
      SELECT column_name
      FROM information_schema.columns
      WHERE table_name = 'species'
        AND column_name IN ('wcvp_native', 'wcvp_introduced')
    `);

    const existingColumns = checkResult.rows.map(r => r.column_name);

    if (!existingColumns.includes('wcvp_native')) {
      console.log('Adding wcvp_native column...');
      await client.query('ALTER TABLE species ADD COLUMN wcvp_native TEXT');
    }

    if (!existingColumns.includes('wcvp_introduced')) {
      console.log('Adding wcvp_introduced column...');
      await client.query('ALTER TABLE species ADD COLUMN wcvp_introduced TEXT');
    }

    console.log('Columns ready.\n');
  } finally {
    client.release();
  }
}

/**
 * Process a batch of updates
 */
async function processBatch(updates) {
  if (updates.length === 0) return;

  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    for (const update of updates) {
      const { taxonFull, wcvpNative, wcvpIntroduced } = update;

      try {
        const result = await client.query(`
          UPDATE species
          SET wcvp_native = $1, wcvp_introduced = $2
          WHERE taxon_full = $3
        `, [wcvpNative, wcvpIntroduced, taxonFull]);

        if (result.rowCount > 0) {
          stats.updatedSpecies++;
        } else {
          stats.notFoundInDb++;
        }
      } catch (err) {
        stats.errors++;
        console.error(`Error updating ${taxonFull}:`, err.message);
      }
    }

    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Main import function
 */
async function importWCVPData() {
  console.log('='.repeat(60));
  console.log('WCVP Native/Introduced Status Import');
  console.log('='.repeat(60));
  console.log(`Source: ${CSV_FILE}\n`);

  // Ensure columns exist
  await ensureColumns();

  // Read CSV and find column indices
  const fileStream = fs.createReadStream(CSV_FILE);
  const rl = readline.createInterface({
    input: fileStream,
    crlfDelay: Infinity
  });

  let headers = null;
  let taxonFullIdx, wcvpNativeIdx, wcvpIntroducedIdx;
  let batch = [];
  let lineNum = 0;

  for await (const line of rl) {
    lineNum++;

    if (lineNum === 1) {
      // Parse headers
      headers = parseCSVLine(line);
      // Use taxon_full to match - this is consistent between CSV and DB
      taxonFullIdx = headers.indexOf('taxon_full');
      wcvpNativeIdx = headers.indexOf('wcvp_native');
      wcvpIntroducedIdx = headers.indexOf('wcvp_introduced');

      console.log(`Column indices: taxon_full=${taxonFullIdx}, wcvp_native=${wcvpNativeIdx}, wcvp_introduced=${wcvpIntroducedIdx}`);

      if (taxonFullIdx === -1 || wcvpNativeIdx === -1 || wcvpIntroducedIdx === -1) {
        throw new Error('Required columns not found in CSV');
      }
      continue;
    }

    stats.totalRows++;

    const fields = parseCSVLine(line);
    const taxonFull = fields[taxonFullIdx] || '';
    let wcvpNative = fields[wcvpNativeIdx] || '';
    let wcvpIntroduced = fields[wcvpIntroducedIdx] || '';

    // Convert 'NA' to null
    if (wcvpNative === 'NA' || wcvpNative === '') wcvpNative = null;
    if (wcvpIntroduced === 'NA' || wcvpIntroduced === '') wcvpIntroduced = null;

    // Skip rows with no WCVP data or no taxon_full
    if (!taxonFull || (!wcvpNative && !wcvpIntroduced)) {
      stats.skippedNoData++;
      continue;
    }

    batch.push({ taxonFull, wcvpNative, wcvpIntroduced });

    // Process batch when full
    if (batch.length >= BATCH_SIZE) {
      await processBatch(batch);
      batch = [];

      // Progress update
      if (stats.totalRows % 10000 === 0) {
        console.log(`Processed ${stats.totalRows.toLocaleString()} rows, ${stats.updatedSpecies.toLocaleString()} species updated...`);
      }
    }
  }

  // Process remaining batch
  if (batch.length > 0) {
    await processBatch(batch);
  }

  // Print summary
  console.log('\n' + '='.repeat(60));
  console.log('Import Complete');
  console.log('='.repeat(60));
  console.log(`Total CSV rows:        ${stats.totalRows.toLocaleString()}`);
  console.log(`Species updated:       ${stats.updatedSpecies.toLocaleString()}`);
  console.log(`Skipped (no data):     ${stats.skippedNoData.toLocaleString()}`);
  console.log(`Not found in DB:       ${stats.notFoundInDb.toLocaleString()}`);
  console.log(`Errors:                ${stats.errors.toLocaleString()}`);
}

// Verify results
async function verifyImport() {
  console.log('\n' + '='.repeat(60));
  console.log('Verification');
  console.log('='.repeat(60));

  const result = await pool.query(`
    SELECT
      COUNT(*) as total,
      COUNT(wcvp_native) as with_native,
      COUNT(wcvp_introduced) as with_introduced,
      COUNT(CASE WHEN wcvp_native IS NOT NULL OR wcvp_introduced IS NOT NULL THEN 1 END) as with_any
    FROM species
  `);

  const row = result.rows[0];
  console.log(`Total species:         ${parseInt(row.total).toLocaleString()}`);
  console.log(`With wcvp_native:      ${parseInt(row.with_native).toLocaleString()}`);
  console.log(`With wcvp_introduced:  ${parseInt(row.with_introduced).toLocaleString()}`);
  console.log(`With any WCVP data:    ${parseInt(row.with_any).toLocaleString()}`);

  // Sample
  console.log('\nSample records:');
  const sample = await pool.query(`
    SELECT taxon_id, species_scientific_name,
           LEFT(wcvp_native, 60) as wcvp_native_sample,
           LEFT(wcvp_introduced, 60) as wcvp_introduced_sample
    FROM species
    WHERE wcvp_native IS NOT NULL
    LIMIT 5
  `);

  for (const row of sample.rows) {
    console.log(`  ${row.taxon_id}: ${row.species_scientific_name}`);
    console.log(`    Native: ${row.wcvp_native_sample}${row.wcvp_native_sample?.length >= 60 ? '...' : ''}`);
    if (row.wcvp_introduced_sample) {
      console.log(`    Introduced: ${row.wcvp_introduced_sample}`);
    }
  }
}

// Run
async function main() {
  try {
    await importWCVPData();
    await verifyImport();
  } catch (err) {
    console.error('Fatal error:', err);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

main();
