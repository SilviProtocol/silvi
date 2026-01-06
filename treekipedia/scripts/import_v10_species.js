#!/usr/bin/env node
/**
 * Treekipedia v10 Species Data Import Script
 *
 * Imports species data from v10 CSV file (1.3 GB)
 * - Updates existing species by taxon_id
 * - Preserves NFT research data (ipfs_cid, researched flag)
 * - Handles new species with INSERT
 * - Maps CSV column names to database column names
 * - Streams CSV to handle large file size
 *
 * Usage:
 *   node import_v10_species.js <csv_file_path> [--dry-run] [--batch-size=1000]
 */

const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');
const csv = require('csv-parser');
const { Transform } = require('stream');
require('dotenv').config({ path: path.join(__dirname, '../.env') });

// Parse command line arguments
const args = process.argv.slice(2);
const csvFilePath = args.find(arg => !arg.startsWith('--')) || './Treekipedia_V10_Final_Climate_October_21d.csv';
const isDryRun = args.includes('--dry-run');
const batchSizeArg = args.find(arg => arg.startsWith('--batch-size='));
const BATCH_SIZE = batchSizeArg ? parseInt(batchSizeArg.split('=')[1]) : 1000;
const LOG_INTERVAL = 5000;

// Database connection
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
});

// Track statistics
const stats = {
  totalRows: 0,
  updatedSpecies: 0,
  newSpecies: 0,
  skippedRows: 0,
  errors: 0,
  preservedNFTData: 0,
  newSpeciesList: [],
  errorList: []
};

// Cache for species with NFT data (to preserve their ipfs_cid and researched status)
let nftSpeciesCache = null;

/**
 * Load list of species that have NFT data (must be preserved)
 */
async function loadNFTSpecies() {
  const query = `
    SELECT DISTINCT taxon_id
    FROM contreebution_nfts
  `;
  try {
    const result = await pool.query(query);
    nftSpeciesCache = new Set(result.rows.map(r => r.taxon_id));
    console.log(`📋 Loaded ${nftSpeciesCache.size} species with NFT data to preserve`);
    return nftSpeciesCache;
  } catch (error) {
    console.error('Error loading NFT species:', error.message);
    process.exit(1);
  }
}

/**
 * Map CSV column names to database column names
 * Handles case differences (e.g., "Soil_texture_all" -> "soil_texture_all")
 * CRITICAL: CSV uses taxon_id_new to match database's taxon_id
 */
function mapColumnName(csvColumnName) {
  // Convert to lowercase for consistency
  const lowerName = csvColumnName.toLowerCase();

  // Special mappings for known differences
  const mappings = {
    'comercialspecies': 'comercialspecies_lower',
    'species': 'species_scientific_name',
    // CSV taxon_id_new maps to database taxon_id for matching
    'taxon_id_new': 'taxon_id',
    // Climate fields - normalize to lowercase with underscores
    'climate_type_koppengeiger': 'climate_type_koppengeiger',
    'annual_temperature_range_c': 'annual_temperature_range_c',
    'annual_precipitation_mm': 'annual_precipitation_mm',
    'wettest_month_precipitation_mm': 'wettest_month_precipitation_mm',
    'driest_month_precipitation_mm': 'driest_month_precipitation_mm',
    'precipitation_seasonality_cv': 'precipitation_seasonality_cv',
    'wettest_quarter_precipitation_mm': 'wettest_quarter_precipitation_mm',
    'driest_quarter_precipitation_mm': 'driest_quarter_precipitation_mm'
  };

  return mappings[lowerName] || lowerName;
}

/**
 * Build UPDATE query for a batch of species
 * CRITICAL: Match on taxon_full, but NEVER update taxon_id (keep existing)
 */
function buildUpdateQuery(speciesData, oldTaxonId) {
  const hasNFT = nftSpeciesCache.has(oldTaxonId);

  // Get all CSV columns EXCEPT:
  // - taxon_full (our matching key)
  // - taxon_id (we keep our existing taxon_id, ignore v10's new IDs)
  const columns = Object.keys(speciesData).filter(col =>
    col !== 'taxon_full' && col !== 'taxon_id'
  );

  // Filter out ipfs_cid and researched if this species has NFT data
  const columnsToUpdate = columns.filter(col => {
    if (hasNFT && (col === 'ipfs_cid' || col === 'researched')) {
      return false; // Skip these columns to preserve NFT data
    }
    return true;
  });

  // Build SET clause
  const setClause = columnsToUpdate
    .map((col, idx) => `${col} = $${idx + 2}`)
    .join(', ');

  // Build values array - match on taxon_full
  const values = [speciesData.taxon_full, ...columnsToUpdate.map(col => speciesData[col])];

  const query = `
    UPDATE species
    SET ${setClause},
        updated_at = NOW()
    WHERE taxon_full = $1
  `;

  return { query, values, hasNFT, oldTaxonId };
}

/**
 * Build INSERT query for new species
 */
function buildInsertQuery(speciesData) {
  const columns = Object.keys(speciesData);
  const placeholders = columns.map((_, idx) => `$${idx + 1}`).join(', ');
  const values = columns.map(col => speciesData[col]);

  const query = `
    INSERT INTO species (${columns.join(', ')}, created_at, updated_at)
    VALUES (${placeholders}, NOW(), NOW())
  `;

  return { query, values };
}

/**
 * Process a batch of species records
 * CRITICAL: Match on taxon_full, preserve old taxon_id for NFT checking
 */
async function processBatch(batch) {
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    for (const speciesData of batch) {
      try {
        // CRITICAL: Match on taxon_full, get the old taxon_id for NFT checking
        const checkResult = await client.query(
          'SELECT taxon_id FROM species WHERE taxon_full = $1',
          [speciesData.taxon_full]
        );

        if (checkResult.rows.length > 0) {
          // Species exists - UPDATE (including updating taxon_id to new value)
          const oldTaxonId = checkResult.rows[0].taxon_id;
          const { query, values, hasNFT } = buildUpdateQuery(speciesData, oldTaxonId);

          if (!isDryRun) {
            await client.query(query, values);
          }

          stats.updatedSpecies++;
          if (hasNFT) {
            stats.preservedNFTData++;
          }
        } else {
          // New species - INSERT
          const { query, values } = buildInsertQuery(speciesData);

          if (!isDryRun) {
            await client.query(query, values);
          }

          stats.newSpecies++;
          stats.newSpeciesList.push(speciesData.taxon_id);
        }
      } catch (error) {
        stats.errors++;
        stats.errorList.push({
          taxon_id: speciesData.taxon_id,
          taxon_full: speciesData.taxon_full,
          error: error.message
        });
        console.error(`Error processing ${speciesData.taxon_full}:`, error.message);
      }
    }

    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    console.error('Batch processing error:', error.message);
    throw error;
  } finally {
    client.release();
  }
}

/**
 * Main import function
 */
async function importV10CSV() {
  console.log('🌳 Treekipedia v10 Species Import');
  console.log('=====================================');
  console.log(`CSV File: ${csvFilePath}`);
  console.log(`Batch Size: ${BATCH_SIZE}`);
  console.log(`Dry Run: ${isDryRun ? 'YES (no changes will be made)' : 'NO (database will be updated)'}`);
  console.log('');

  // Check file exists
  if (!fs.existsSync(csvFilePath)) {
    console.error(`❌ File not found: ${csvFilePath}`);
    process.exit(1);
  }

  const fileStats = fs.statSync(csvFilePath);
  console.log(`📁 File size: ${(fileStats.size / 1024 / 1024 / 1024).toFixed(2)} GB`);
  console.log('');

  // Load NFT species to preserve their data
  await loadNFTSpecies();
  console.log('');

  const startTime = Date.now();
  let batch = [];

  return new Promise((resolve, reject) => {
    // Create transform stream for batch processing
    const batchProcessor = new Transform({
      objectMode: true,
      transform(row, encoding, callback) {
        stats.totalRows++;

        // Skip rows with missing taxon_full (this is our matching key)
        if (!row.taxon_full || row.taxon_full.trim() === '') {
          stats.skippedRows++;
          console.warn(`Row ${stats.totalRows}: Missing taxon_full, skipping`);
          callback();
          return;
        }

        // Map CSV columns to database columns
        const mappedRow = {};
        for (const [csvCol, value] of Object.entries(row)) {
          const dbCol = mapColumnName(csvCol);

          // Skip the old taxon_id column (we use taxon_id_new instead)
          if (csvCol.toLowerCase() === 'taxon_id') {
            continue;
          }

          // Convert empty strings to null
          mappedRow[dbCol] = value === '' ? null : value;
        }

        batch.push(mappedRow);

        // Process batch when full
        if (batch.length >= BATCH_SIZE) {
          const currentBatch = [...batch];
          batch = [];

          processBatch(currentBatch)
            .then(() => callback())
            .catch(err => callback(err));
        } else {
          callback();
        }

        // Log progress
        if (stats.totalRows % LOG_INTERVAL === 0) {
          const elapsed = (Date.now() - startTime) / 1000;
          const rate = stats.totalRows / elapsed;
          console.log(`📊 Progress: ${stats.totalRows.toLocaleString()} rows | ` +
                     `${stats.updatedSpecies.toLocaleString()} updated | ` +
                     `${stats.newSpecies.toLocaleString()} new | ` +
                     `${rate.toFixed(0)} rows/sec`);
        }
      },

      async flush(callback) {
        // Process remaining batch
        if (batch.length > 0) {
          try {
            await processBatch(batch);
            callback();
          } catch (err) {
            callback(err);
          }
        } else {
          callback();
        }
      }
    });

    // Start streaming CSV
    fs.createReadStream(csvFilePath)
      .pipe(csv())
      .pipe(batchProcessor)
      .on('finish', async () => {
        const elapsed = (Date.now() - startTime) / 1000;

        console.log('');
        console.log('✅ Import Complete!');
        console.log('=====================================');
        console.log(`⏱️  Duration: ${(elapsed / 60).toFixed(2)} minutes`);
        console.log(`📊 Total rows processed: ${stats.totalRows.toLocaleString()}`);
        console.log(`✏️  Species updated: ${stats.updatedSpecies.toLocaleString()}`);
        console.log(`➕ New species added: ${stats.newSpecies.toLocaleString()}`);
        console.log(`🔒 NFT data preserved: ${stats.preservedNFTData.toLocaleString()} species`);
        console.log(`⏭️  Rows skipped: ${stats.skippedRows.toLocaleString()}`);
        console.log(`❌ Errors: ${stats.errors.toLocaleString()}`);

        if (stats.newSpecies > 0 && stats.newSpecies <= 50) {
          console.log('');
          console.log('New species added:');
          stats.newSpeciesList.forEach(id => console.log(`  - ${id}`));
        }

        if (stats.errors > 0 && stats.errors <= 20) {
          console.log('');
          console.log('Errors encountered:');
          stats.errorList.forEach(err => console.log(`  - ${err.taxon_id}: ${err.error}`));
        }

        if (isDryRun) {
          console.log('');
          console.log('🔵 DRY RUN - No changes were made to the database');
        }

        await pool.end();
        resolve();
      })
      .on('error', (error) => {
        console.error('❌ CSV parsing error:', error.message);
        reject(error);
      });
  });
}

// Run the import
importV10CSV()
  .then(() => {
    console.log('');
    console.log('🎉 Import script finished successfully');
    process.exit(0);
  })
  .catch((error) => {
    console.error('');
    console.error('💥 Import script failed:', error.message);
    process.exit(1);
  });
