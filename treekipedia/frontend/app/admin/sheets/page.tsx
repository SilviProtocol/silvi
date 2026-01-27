'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Sheet, CheckCircle, AlertCircle } from 'lucide-react';

interface SheetsResult {
  success: boolean;
  ontology_path?: string;
  sheets_processed?: string[];
  field_detection?: Record<string, string>;
  error?: string;
}

export default function SheetsPage() {
  const [spreadsheetId, setSpreadsheetId] = useState('');
  const [sheetNames, setSheetNames] = useState('');
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<SheetsResult | null>(null);

  const handleImport = async () => {
    if (!spreadsheetId.trim()) {
      alert('Please enter a Google Sheets ID');
      return;
    }

    setImporting(true);
    setResult(null);

    try {
      const response = await fetch('http://localhost:5001/api/admin/ontology/from-sheets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          spreadsheetId: spreadsheetId.trim(),
          sheets: sheetNames.trim() ? sheetNames.split(',').map((s) => s.trim()) : undefined,
        }),
      });

      const data: SheetsResult = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Import failed');
      }

      setResult(data);
    } catch (error) {
      console.error('Import failed:', error);
      setResult({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-emerald-950 to-gray-900">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="mb-8">
          <Link href="/admin" className="flex items-center gap-2 text-emerald-400 hover:text-emerald-300 mb-4">
            <ArrowLeft className="w-4 h-4" />
            Back to Admin
          </Link>
          <h1 className="text-4xl font-bold text-emerald-300 mb-2">
            Google Sheets Import
          </h1>
          <p className="text-gray-400">
            Import biodiversity data from Google Sheets and generate ontologies
          </p>
        </div>

        <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6 mb-6">
          <h2 className="text-xl font-semibold text-emerald-300 mb-4">
            Spreadsheet Configuration
          </h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Google Sheets ID *
              </label>
              <input
                type="text"
                value={spreadsheetId}
                onChange={(e) => setSpreadsheetId(e.target.value)}
                placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
                className="w-full px-4 py-2 bg-black/40 border border-white/20 rounded-lg text-white focus:outline-none focus:border-emerald-500"
              />
              <p className="text-xs text-gray-400 mt-1">
                From the spreadsheet URL: https://docs.google.com/spreadsheets/d/<strong>SPREADSHEET_ID</strong>/edit
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Sheet Names (Optional)
              </label>
              <input
                type="text"
                value={sheetNames}
                onChange={(e) => setSheetNames(e.target.value)}
                placeholder="Sheet1, Sheet2, Sheet3"
                className="w-full px-4 py-2 bg-black/40 border border-white/20 rounded-lg text-white focus:outline-none focus:border-emerald-500"
              />
              <p className="text-xs text-gray-400 mt-1">
                Comma-separated sheet names. Leave empty to process all sheets.
              </p>
            </div>

            <button
              onClick={handleImport}
              disabled={importing || !spreadsheetId.trim()}
              className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Sheet className="w-5 h-5" />
              {importing ? 'Importing...' : 'Import from Google Sheets'}
            </button>
          </div>
        </div>

        {result && (
          <div className="space-y-6">
            {result.success ? (
              <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-6">
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-emerald-300 font-semibold mb-1">
                      Import Successful!
                    </h3>
                    <p className="text-sm text-gray-300">
                      {result.sheets_processed?.length || 0} sheet(s) processed
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-red-300 font-semibold mb-1">Import Failed</h3>
                    <p className="text-sm text-gray-300">{result.error}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
