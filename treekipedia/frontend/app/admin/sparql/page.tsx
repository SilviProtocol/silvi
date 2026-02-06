'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Play, Download } from 'lucide-react';
import DataTable from '../components/DataTable';

const EXAMPLE_QUERIES = [
  {
    name: 'Get All Species (First 10)',
    query: `PREFIX bd: <http://www.example.org/biodiversity-ontology#>
SELECT ?species ?name WHERE {
  ?species bd:scientificName ?name .
} LIMIT 10`,
  },
  {
    name: 'Count Total Triples',
    query: `SELECT (COUNT(*) as ?count) WHERE {
  ?s ?p ?o .
}`,
  },
  {
    name: 'Find Species by Family',
    query: `PREFIX bd: <http://www.example.org/biodiversity-ontology#>
SELECT ?species ?name ?family WHERE {
  ?species bd:scientificName ?name .
  ?species bd:family ?family .
  FILTER(?family = "Fagaceae")
} LIMIT 20`,
  },
];

export default function SparqlPage() {
  const [query, setQuery] = useState(EXAMPLE_QUERIES[0].query);
  const [executing, setExecuting] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const executeQuery = async () => {
    setExecuting(true);
    setError(null);
    setResults(null);

    try {
      const response = await fetch('http://localhost:5001/api/admin/sparql/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Query failed');
      }

      setResults(data.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setExecuting(false);
    }
  };

  const exportResults = () => {
    if (!results) return;
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sparql-results.json';
    a.click();
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-emerald-950 to-gray-900">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <div className="mb-8">
          <Link href="/admin" className="flex items-center gap-2 text-emerald-400 hover:text-emerald-300 mb-4">
            <ArrowLeft className="w-4 h-4" />
            Back to Admin
          </Link>
          <h1 className="text-4xl font-bold text-emerald-300 mb-2">
            SPARQL Query Editor
          </h1>
          <p className="text-gray-400">
            Query the Fuseki knowledge graph using SPARQL
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1">
            <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-4 sticky top-4">
              <h2 className="text-lg font-semibold text-emerald-300 mb-4">
                Example Queries
              </h2>
              <div className="space-y-2">
                {EXAMPLE_QUERIES.map((example, index) => (
                  <button
                    key={index}
                    onClick={() => setQuery(example.query)}
                    className="w-full text-left px-3 py-2 bg-black/40 hover:bg-emerald-500/20 border border-white/10 hover:border-emerald-500/30 rounded-lg text-sm text-gray-300 transition-colors"
                  >
                    {example.name}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="lg:col-span-3 space-y-6">
            <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-emerald-300">
                  Query Editor
                </h2>
                <button
                  onClick={executeQuery}
                  disabled={executing}
                  className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-lg transition-colors disabled:opacity-50"
                >
                  <Play className="w-4 h-4" />
                  {executing ? 'Executing...' : 'Execute Query'}
                </button>
              </div>

              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full h-64 px-4 py-3 bg-black/60 border border-white/20 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-emerald-500 resize-none"
                placeholder="Enter your SPARQL query here..."
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                <p className="text-red-400">{error}</p>
              </div>
            )}

            {results && (
              <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-emerald-300">
                    Results
                  </h2>
                  <button
                    onClick={exportResults}
                    className="flex items-center gap-2 px-3 py-2 bg-gray-600 hover:bg-gray-500 text-white rounded-lg transition-colors text-sm"
                  >
                    <Download className="w-4 h-4" />
                    Export JSON
                  </button>
                </div>

                <pre className="p-4 bg-black/60 rounded-lg overflow-x-auto">
                  <code className="text-sm text-gray-300">
                    {JSON.stringify(results, null, 2)}
                  </code>
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
