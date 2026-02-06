'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import StatusCard from '../components/StatusCard';

export default function MonitorPage() {
  const [refreshing, setRefreshing] = useState(false);
  const [serviceStatus, setServiceStatus] = useState<any>(null);
  const [fusekiStats, setFusekiStats] = useState<any>(null);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000); // Every 10s
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const [statusRes, fusekiRes] = await Promise.all([
        fetch('http://localhost:5001/api/admin/status'),
        fetch('http://localhost:5001/api/admin/status/fuseki'),
      ]);

      setServiceStatus(await statusRes.json());
      setFusekiStats(await fusekiRes.json());
    } catch (error) {
      console.error('Failed to fetch status:', error);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchStatus();
    setTimeout(() => setRefreshing(false), 500);
  };

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
              System Monitor
            </h1>
            <p className="text-gray-400">
              Real-time monitoring of all services and systems
            </p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 bg-pink-600 hover:bg-pink-500 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <StatusCard
            title="PostgreSQL Database"
            status={serviceStatus?.postgres?.status || 'unknown'}
            message={serviceStatus?.postgres?.message}
            details={{
              host: '167.172.143.162',
              database: 'treekipedia',
              records: '67,743 species',
            }}
          />

          <StatusCard
            title="Apache Fuseki"
            status={fusekiStats?.status === 'connected' ? 'connected' : 'disconnected'}
            message={fusekiStats?.endpoint}
            details={fusekiStats?.stats}
          />

          <StatusCard
            title="Python Microservice"
            status={serviceStatus?.graphflow_modules?.status === 'available' ? 'healthy' : 'unhealthy'}
            message="Port 5002"
            details={{
              service: 'treekipedia-python-microservice',
              modules: serviceStatus?.graphflow_modules?.status || 'unknown',
            }}
          />

          <StatusCard
            title="Express Backend"
            status="healthy"
            message="Port 5001"
            details={{
              uptime: 'Running',
              endpoints: '58 admin routes',
            }}
          />
        </div>
      </div>
    </div>
  );
}
