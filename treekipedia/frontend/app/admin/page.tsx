'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Activity,
  Database,
  FileText,
  Sheet,
  Search,
  GitBranch,
  ArrowRight,
} from 'lucide-react';
import StatusCard, { StatusType } from './components/StatusCard';

interface ServiceStatus {
  postgres?: { status: StatusType; message: string };
  fuseki?: { status: StatusType; message: string };
  graphflow_modules?: { status: string };
}

interface FusekiStats {
  status: string;
  endpoint?: string;
  dataset?: string;
  stats?: {
    triples?: number;
    graphs?: number;
  };
}

export default function AdminDashboard() {
  const router = useRouter();
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);
  const [fusekiStats, setFusekiStats] = useState<FusekiStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      // Fetch general status
      const statusRes = await fetch('http://localhost:5001/api/admin/status');
      const statusData = await statusRes.json();
      setServiceStatus(statusData);

      // Fetch Fuseki stats
      const fusekiRes = await fetch('http://localhost:5001/api/admin/status/fuseki');
      const fusekiData = await fusekiRes.json();
      setFusekiStats(fusekiData);
    } catch (error) {
      console.error('Failed to fetch status:', error);
    } finally {
      setLoading(false);
    }
  };

  const quickActions = [
    {
      title: 'Sync Species',
      description: 'Sync PostgreSQL species data to Fuseki',
      icon: Database,
      href: '/admin/sync',
      color: 'emerald',
    },
    {
      title: 'Upload CSV',
      description: 'Generate ontology from CSV files',
      icon: FileText,
      href: '/admin/upload',
      color: 'blue',
    },
    {
      title: 'Google Sheets',
      description: 'Import from Google Sheets',
      icon: Sheet,
      href: '/admin/sheets',
      color: 'purple',
    },
    {
      title: 'SPARQL Query',
      description: 'Query the knowledge graph',
      icon: Search,
      href: '/admin/sparql',
      color: 'orange',
    },
    {
      title: 'System Monitor',
      description: 'Monitor system health',
      icon: Activity,
      href: '/admin/monitor',
      color: 'pink',
    },
    {
      title: 'Version Control',
      description: 'Manage ontology versions',
      icon: GitBranch,
      href: '/admin/versions',
      color: 'cyan',
    },
  ];

  const getColorClasses = (color: string) => {
    const colors: Record<string, { bg: string; border: string; text: string; hover: string }> = {
      emerald: {
        bg: 'bg-emerald-500/10',
        border: 'border-emerald-500/30',
        text: 'text-emerald-400',
        hover: 'hover:bg-emerald-500/20',
      },
      blue: {
        bg: 'bg-blue-500/10',
        border: 'border-blue-500/30',
        text: 'text-blue-400',
        hover: 'hover:bg-blue-500/20',
      },
      purple: {
        bg: 'bg-purple-500/10',
        border: 'border-purple-500/30',
        text: 'text-purple-400',
        hover: 'hover:bg-purple-500/20',
      },
      orange: {
        bg: 'bg-orange-500/10',
        border: 'border-orange-500/30',
        text: 'text-orange-400',
        hover: 'hover:bg-orange-500/20',
      },
      pink: {
        bg: 'bg-pink-500/10',
        border: 'border-pink-500/30',
        text: 'text-pink-400',
        hover: 'hover:bg-pink-500/20',
      },
      cyan: {
        bg: 'bg-cyan-500/10',
        border: 'border-cyan-500/30',
        text: 'text-cyan-400',
        hover: 'hover:bg-cyan-500/20',
      },
    };
    return colors[color] || colors.emerald;
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-emerald-950 to-gray-900">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-4xl font-bold text-emerald-300 mb-2">
              Admin Portal
            </h1>
            <p className="text-gray-400">
              Manage GraphFlow ontology generation and species data synchronization
            </p>
          </div>
          <Link
            href="/"
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
          >
            ← Back to Treekipedia
          </Link>
        </div>

        {/* Service Status */}
        <div className="mb-8">
          <h2 className="text-2xl font-semibold text-emerald-300 mb-4">
            Service Status
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatusCard
              title="PostgreSQL"
              status={loading ? 'loading' : (serviceStatus?.postgres?.status || 'unknown')}
              message={serviceStatus?.postgres?.message}
            />
            <StatusCard
              title="Apache Fuseki"
              status={loading ? 'loading' : (fusekiStats?.status === 'connected' ? 'connected' : 'disconnected')}
              message={fusekiStats?.endpoint}
              details={
                fusekiStats?.stats
                  ? {
                      triples: fusekiStats.stats.triples?.toLocaleString() || '0',
                      graphs: fusekiStats.stats.graphs || 0,
                      dataset: fusekiStats.dataset || 'N/A',
                    }
                  : undefined
              }
            />
            <StatusCard
              title="GraphFlow Modules"
              status={
                loading
                  ? 'loading'
                  : serviceStatus?.graphflow_modules?.status === 'available'
                  ? 'healthy'
                  : 'unhealthy'
              }
              message={
                serviceStatus?.graphflow_modules?.status === 'available'
                  ? 'All Python modules loaded'
                  : 'Some modules unavailable (install dependencies)'
              }
            />
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mb-8">
          <h2 className="text-2xl font-semibold text-emerald-300 mb-4">
            Quick Actions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {quickActions.map((action) => {
              const colors = getColorClasses(action.color);
              const Icon = action.icon;

              return (
                <button
                  key={action.href}
                  onClick={() => router.push(action.href)}
                  className={`bg-black/30 backdrop-blur-md border ${colors.border} rounded-xl p-6 text-left transition-all ${colors.hover} group`}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className={`${colors.bg} p-3 rounded-lg`}>
                      <Icon className={`w-6 h-6 ${colors.text}`} />
                    </div>
                    <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-emerald-400 transition-colors" />
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">
                    {action.title}
                  </h3>
                  <p className="text-sm text-gray-400">{action.description}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Recent Activity */}
        <div>
          <h2 className="text-2xl font-semibold text-emerald-300 mb-4">
            Recent Activity
          </h2>
          <div className="bg-black/30 backdrop-blur-md border border-white/20 rounded-xl p-6">
            <p className="text-gray-400 text-center py-8">
              Activity logging coming soon...
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
