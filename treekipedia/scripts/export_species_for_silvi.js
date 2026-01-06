#!/usr/bin/env node

/**
 * Export species data for Silvi's Django backend
 * Outputs CSV with exact field names matching Silvi's Species model
 */

const { Pool } = require('pg');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: '../.env' });

// Database connection
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

async function exportSpeciesForSilvi() {
  const client = await pool.connect();

  try {
    console.log('🌳 Exporting species data for Silvi...\n');

    // Query to get only the fields matching Silvi's Django model
    const query = `
      SELECT
        taxon_id,
        common_name as species_common_name,
        species_scientific_name,
        subspecies,
        genus,
        family,
        class as taxonomic_class,
        taxonomic_order
      FROM species
      ORDER BY taxon_id;
    `;

    console.log('📊 Querying database...');
    const result = await client.query(query);

    console.log(`✅ Found ${result.rows.length.toLocaleString()} species\n`);

    // Create CSV content
    const headers = [
      'taxon_id',
      'species_common_name',
      'species_scientific_name',
      'subspecies',
      'genus',
      'family',
      'taxonomic_class',
      'taxonomic_order'
    ];

    let csvContent = headers.join(',') + '\n';

    // Add data rows
    for (const row of result.rows) {
      const values = headers.map(header => {
        const value = row[header];
        // Handle null/undefined values and escape commas/quotes
        if (value === null || value === undefined) {
          return '';
        }
        // Escape quotes and wrap in quotes if contains comma or quote
        const stringValue = String(value);
        if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
          return `"${stringValue.replace(/"/g, '""')}"`;
        }
        return stringValue;
      });
      csvContent += values.join(',') + '\n';
    }

    // Write to file
    const outputPath = path.join(__dirname, '..', 'exports', 'treekipedia_species_for_silvi.csv');

    // Create exports directory if it doesn't exist
    const exportsDir = path.join(__dirname, '..', 'exports');
    if (!fs.existsSync(exportsDir)) {
      fs.mkdirSync(exportsDir, { recursive: true });
    }

    fs.writeFileSync(outputPath, csvContent);

    console.log('✅ CSV export completed successfully!');
    console.log(`📄 Output file: ${outputPath}`);
    console.log(`📊 Total records: ${result.rows.length.toLocaleString()}`);
    console.log(`💾 File size: ${(csvContent.length / 1024 / 1024).toFixed(2)} MB`);

    // Show sample of first few rows
    console.log('\n📋 Sample data (first 3 rows):');
    console.log(headers.join(' | '));
    console.log('-'.repeat(headers.join(' | ').length));
    for (let i = 0; i < Math.min(3, result.rows.length); i++) {
      const values = headers.map(h => {
        const val = result.rows[i][h];
        return val ? String(val).substring(0, 20) : 'NULL';
      });
      console.log(values.join(' | '));
    }

  } catch (error) {
    console.error('❌ Error exporting species data:', error);
    throw error;
  } finally {
    client.release();
  }
}

async function main() {
  try {
    await exportSpeciesForSilvi();
    console.log('\n🎉 Export complete!');
  } catch (error) {
    console.error('\n❌ Export failed:', error.message);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

// Run the script
if (require.main === module) {
  main();
}

module.exports = { exportSpeciesForSilvi };
