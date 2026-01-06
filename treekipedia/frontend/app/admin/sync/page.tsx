'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Play, Pause, RotateCcw, CheckCircle } from 'lucide-react';
import ProgressBar from '../components/ProgressBar';

interface SyncEvent {
  type: 'status' | 'progress' | 'complete' | 'error';
  message: string;
  progress?: number;
}

export default function SyncPage() {
  const [syncing, setSyncing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'idle' | 'running' | 'complete' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [logs, setLogs] = useState<string[]>([]);
  const [batchSize, setBatchSize] = useState(1000);

  const addLog = (msg: string) => {
    setLogs((prev) => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] ${msg}`
    ].slice(-50)); // Keep last 50 logs
  };

  const startSync = async () => {
    setSyncing(true);
    setStatus('running');
    setProgress(0);
    setLogs([]);
    setMessage('Initiating sync...');
    addLog('Starting sync process...');

    try {
      const response = await fetch('http://localhost:5001/api/admin/sync/species', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ batchSize }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          addLog('Stream ended');
          break;
        }

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data: SyncEvent = JSON.parse(line.slice(6));

              addLog(`${data.type.toUpperCase()}: ${data.message}`);
              setMessage(data.message);

              if (data.type === 'progress' && data.progress !== undefined) {
                setProgress(data.progress);
              } else if (data.type === 'complete') {
                setStatus('complete');
                setProgress(100);
                setSyncing(false);
              } else if (data.type === 'error') {
                setStatus('error');
                setSyncing(false);
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Sync failed:', error);
      setStatus('error');
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      addLog(`ERROR: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setSyncing(false);
    }
  };

  const resetSync = () => {
    setStatus('idle');
    setProgress(0);
    setMessage('');
    setLogs([]);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-emerald-950 to-gray-900">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <Link
              href="/admin"
              className="flex items-center gap-2 text-emerald-400 hover:text-emerald-300 mb-4"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Admin
            </Link>
            <h1 className="text-4xl font-bold text-emerald-300 mb-2">
              PostgreSQL → Fuseki Sync
            </h1>
            <p className="text-gray-400">
              Sync 67,743 species from PostgreSQL to Apache Fuseki triple store
            </p>
          </div>
        </div>

        {/* Sync Configuration */}
        <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6 mb-6">
          <h2 className="text-xl font-semibold text-emerald-300 mb-4">
            Sync Configuration
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Batch Size
              </label>
              <input
                type="number"
                value={batchSize}
                onChange={(e) => setBatchSize(parseInt(e.target.value))}
                disabled={syncing}
                className="w-full px-4 py-2 bg-black/40 border border-white/20 rounded-lg text-white focus:outline-none focus:border-emerald-500 disabled:opacity-50"
                min="100"
                max="5000"
                step="100"
              />
              <p className="text-xs text-gray-400 mt-1">
                Number of species to sync per batch (100-5000)
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Estimated Time
              </label>
              <div className="px-4 py-2 bg-black/40 border border-white/20 rounded-lg text-white">
                {Math.ceil(67743 / batchSize)} batches · ~{Math.ceil((67743 / batchSize) * 2)} minutes
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Approximate sync duration
              </p>
            </div>
          </div>
        </div>

        {/* Progress */}
        <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6 mb-6">
          <h2 className="text-xl font-semibold text-emerald-300 mb-4">
            Sync Progress
          </h2>

          <ProgressBar
            progress={progress}
            status={status}
            message={message}
            className="mb-6"
          />

          {/* Controls */}
          <div className="flex gap-4">
            <button
              onClick={startSync}
              disabled={syncing || status === 'complete'}
              className="flex items-center gap-2 px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-5 h-5" />
              {status === 'running' ? 'Syncing...' : 'Start Sync'}
            </button>

            {status === 'complete' && (
              <button
                onClick={resetSync}
                className="flex items-center gap-2 px-6 py-3 bg-gray-600 hover:bg-gray-500 text-white rounded-lg transition-colors"
              >
                <RotateCcw className="w-5 h-5" />
                Reset
              </button>
            )}

            {status === 'error' && (
              <button
                onClick={resetSync}
                className="flex items-center gap-2 px-6 py-3 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors"
              >
                <RotateCcw className="w-5 h-5" />
                Try Again
              </button>
            )}
          </div>

          {/* Success Message */}
          {status === 'complete' && (
            <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg flex items-start gap-3">
              <CheckCircle className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-emerald-300 font-semibold mb-1">
                  Sync Complete!
                </h3>
                <p className="text-sm text-gray-300">
                  All species data has been successfully synced to Fuseki.
                  You can now run SPARQL queries against the knowledge graph.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Logs */}
        <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6">
          <h2 className="text-xl font-semibold text-emerald-300 mb-4">
            Sync Logs
          </h2>
          <div className="bg-black/60 border border-white/10 rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm">
            {logs.length === 0 ? (
              <p className="text-gray-500 text-center py-8">
                No logs yet. Start sync to see progress...
              </p>
            ) : (
              <div className="space-y-1">
                {logs.map((log, index) => (
                  <div
                    key={index}
                    className={`${
                      log.includes('ERROR')
                        ? 'text-red-400'
                        : log.includes('COMPLETE')
                        ? 'text-emerald-400'
                        : 'text-gray-300'
                    }`}
                  >
                    {log}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Info Card */}
        <div className="mt-6 bg-blue-500/10 border border-blue-500/30 rounded-xl p-6">
          <h3 className="text-blue-300 font-semibold mb-2">
            About PostgreSQL → Fuseki Sync
          </h3>
          <ul className="text-sm text-gray-300 space-y-2">
            <li>• Converts 67,743 species records from PostgreSQL to RDF triples</li>
            <li>• Each species generates ~100 triples (properties, relationships, etc.)</li>
            <li>• Total expected: ~6.7 million triples in Fuseki</li>
            <li>• Uses batch processing for memory efficiency</li>
            <li>• Progress updates streamed in real-time via Server-Sent Events</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
