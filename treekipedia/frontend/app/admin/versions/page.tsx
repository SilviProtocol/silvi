'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Plus, Download, Clock } from 'lucide-react';
import DataTable from '../components/DataTable';

interface Version {
  version: string;
  timestamp: string;
  description: string;
}

export default function VersionsPage() {
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [description, setDescription] = useState('');

  useEffect(() => {
    fetchVersions();
  }, []);

  const fetchVersions = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/admin/versions');
      const data = await response.json();
      setVersions(data.versions || []);
    } catch (error) {
      console.error('Failed to fetch versions:', error);
    } finally {
      setLoading(false);
    }
  };

  const createVersion = async () => {
    setCreating(true);

    try {
      const response = await fetch('http://localhost:5001/api/admin/versions/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ description }),
      });

      if (response.ok) {
        await fetchVersions();
        setShowCreateDialog(false);
        setDescription('');
      }
    } catch (error) {
      console.error('Failed to create version:', error);
    } finally {
      setCreating(false);
    }
  };

  const columns = [
    {
      key: 'version',
      header: 'Version',
      sortable: true,
    },
    {
      key: 'timestamp',
      header: 'Created',
      sortable: true,
      render: (value: string) => new Date(value).toLocaleString(),
    },
    {
      key: 'description',
      header: 'Description',
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (_: any, row: Version) => (
        <button className="text-cyan-400 hover:text-cyan-300 text-sm">
          <Download className="w-4 h-4" />
        </button>
      ),
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-emerald-950 to-gray-900">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <Link href="/admin" className="flex items-center gap-2 text-emerald-400 hover:text-emerald-300 mb-4">
              <ArrowLeft className="w-4 h-4" />
              Back to Admin
            </Link>
            <h1 className="text-4xl font-bold text-emerald-300 mb-2">
              Version Management
            </h1>
            <p className="text-gray-400">
              Create and manage ontology version snapshots
            </p>
          </div>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors"
          >
            <Plus className="w-5 h-5" />
            Create Version
          </button>
        </div>

        {showCreateDialog && (
          <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6 mb-6">
            <h2 className="text-xl font-semibold text-emerald-300 mb-4">
              Create New Version
            </h2>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Version description..."
              className="w-full px-4 py-2 bg-black/40 border border-white/20 rounded-lg text-white focus:outline-none focus:border-emerald-500 mb-4"
            />
            <div className="flex gap-3">
              <button
                onClick={createVersion}
                disabled={creating || !description.trim()}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create'}
              </button>
              <button
                onClick={() => setShowCreateDialog(false)}
                className="px-4 py-2 bg-gray-600 hover:bg-gray-500 text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6">
          <h2 className="text-xl font-semibold text-emerald-300 mb-4">
            Version History
          </h2>
          {loading ? (
            <p className="text-gray-400 text-center py-8">Loading versions...</p>
          ) : (
            <DataTable data={versions} columns={columns} emptyMessage="No versions created yet" />
          )}
        </div>

        <div className="mt-6 bg-cyan-500/10 border border-cyan-500/30 rounded-xl p-6">
          <h3 className="text-cyan-300 font-semibold mb-2">
            About Version Management
          </h3>
          <ul className="text-sm text-gray-300 space-y-2">
            <li>• Snapshots capture the current state of the ontology</li>
            <li>• Each version includes all RDF triples and metadata</li>
            <li>• Versions can be downloaded and restored if needed</li>
            <li>• Automatic version incrementing on sync completion</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
