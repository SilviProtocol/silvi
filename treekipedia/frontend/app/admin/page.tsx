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
  Server,
  BarChart3,
  AlertCircle,
  LogOut,
  RefreshCw,
} from 'lucide-react';
import StatusCard, { StatusType } from './components/StatusCard';

// Simple client-side password - CHANGE THIS to secure your admin page
const ADMIN_PASSWORD = 'onetwotree';

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

type TabType = 'dashboard' | 'stats' | 'api' | 'errors';

export default function AdminDashboard() {
  const router = useRouter();

  // Auth state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');

  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');

  // GraphFlow status state
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);
  const [fusekiStats, setFusekiStats] = useState<FusekiStats | null>(null);

  // Monitoring state
  const [serverStats, setServerStats] = useState<any>(null);
  const [apiCallStats, setApiCallStats] = useState<any>(null);
  const [errorLogs, setErrorLogs] = useState<any>([]);

  const [loading, setLoading] = useState(false);

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

  // Check if user is already logged in (from localStorage)
  useEffect(() => {
    const isLoggedIn = localStorage.getItem('admin_authenticated') === 'true';
    setIsAuthenticated(isLoggedIn);
  }, []);

  const handleLogin = () => {
    if (password === ADMIN_PASSWORD) {
      setIsAuthenticated(true);
      localStorage.setItem('admin_authenticated', 'true');
      setPasswordError('');
    } else {
      setPasswordError('Incorrect password');
    }
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    localStorage.removeItem('admin_authenticated');
  };

  // Fetch all data
  const fetchAllData = async () => {
    setLoading(true);
    try {
      // Fetch GraphFlow status
      try {
        const statusRes = await fetch(`${API_BASE_URL}/api/admin/status`);
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          setServiceStatus(statusData);
        }
      } catch (e) {
        console.error('Failed to fetch GraphFlow status:', e);
      }

      // Fetch Fuseki stats
      try {
        const fusekiRes = await fetch(`${API_BASE_URL}/api/admin/status/fuseki`);
        if (fusekiRes.ok) {
          const fusekiData = await fusekiRes.json();
          setFusekiStats(fusekiData);
        }
      } catch (e) {
        console.error('Failed to fetch Fuseki stats:', e);
      }

      // Fetch server stats and API call stats in parallel
      const [statsRes, callStatsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/admin-api/stats`).catch(() => null),
        fetch(`${API_BASE_URL}/admin-api/call-stats`).catch(() => null),
      ]);

      if (statsRes?.ok) {
        const statsData = await statsRes.json();
        setServerStats(statsData);
      }

      if (callStatsRes?.ok) {
        const callStatsData = await callStatsRes.json();
        setApiCallStats(callStatsData);
      }

      // Only fetch error logs when the errors tab is active
      if (activeTab === 'errors') {
        try {
          const logsRes = await fetch(`${API_BASE_URL}/admin-api/errors?limit=100`);
          if (logsRes.ok) {
            const logsData = await logsRes.json();
            setErrorLogs(logsData.logs || []);
          }
        } catch (e) {
          console.error('Failed to fetch error logs:', e);
        }
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch data when authenticated or tab changes
  useEffect(() => {
    if (isAuthenticated) {
      fetchAllData();
      const interval = setInterval(fetchAllData, 30000); // Refresh every 30s
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, activeTab]);

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

  // Format memory sizes
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Format server uptime
  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / (3600 * 24));
    const hours = Math.floor((seconds % (3600 * 24)) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${mins}m`;
  };

  // Tab definitions
  const tabs = [
    { id: 'dashboard' as TabType, label: 'Dashboard', icon: Activity },
    { id: 'stats' as TabType, label: 'Server Stats', icon: Server },
    { id: 'api' as TabType, label: 'API Usage', icon: BarChart3 },
    { id: 'errors' as TabType, label: 'Error Logs', icon: AlertCircle },
  ];

  // Render login screen if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4 bg-gradient-to-b from-gray-900 via-emerald-950 to-gray-900">
        <div className="w-full max-w-md p-6 bg-black/50 backdrop-blur-lg border border-white/20 rounded-xl shadow-lg">
          <h1 className="text-2xl font-bold text-emerald-300 mb-6">Admin Portal</h1>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
                className="w-full p-3 bg-black/30 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500"
                placeholder="Enter admin password"
              />
              {passwordError && (
                <p className="text-red-400 text-sm mt-1">{passwordError}</p>
              )}
            </div>
            <button
              onClick={handleLogin}
              className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors font-medium"
            >
              Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Render dashboard for authenticated users
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
              Manage GraphFlow ontology generation and monitor system health
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={fetchAllData}
              disabled={loading}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-red-600/70 hover:bg-red-600 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
            <Link
              href="/"
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
            >
              ← Back to Treekipedia
            </Link>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="mb-8 flex space-x-1 border-b border-white/20">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={`px-4 py-3 flex items-center gap-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-b-2 border-emerald-400 text-emerald-400'
                    : 'text-white/70 hover:text-white'
                }`}
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <>
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
          </>
        )}

        {/* Server Stats Tab */}
        {activeTab === 'stats' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <div className="p-6 bg-black/30 backdrop-blur-lg border border-white/20 rounded-xl">
              <h2 className="text-lg font-semibold text-emerald-300 mb-4">Server Information</h2>
              {serverStats ? (
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Uptime:</span>
                    <span className="text-white">{formatUptime(serverStats.serverUptime)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Memory (RSS):</span>
                    <span className="text-white">{formatBytes(serverStats.memoryUsage?.rss || 0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Memory (Heap):</span>
                    <span className="text-white">
                      {formatBytes(serverStats.memoryUsage?.heapUsed || 0)} / {formatBytes(serverStats.memoryUsage?.heapTotal || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Last Updated:</span>
                    <span className="text-white">{new Date(serverStats.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500">Loading server stats...</p>
              )}
            </div>

            <div className="p-6 bg-black/30 backdrop-blur-lg border border-white/20 rounded-xl">
              <h2 className="text-lg font-semibold text-emerald-300 mb-4">API Summary</h2>
              {apiCallStats ? (
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Total API Calls:</span>
                    <span className="text-white">{apiCallStats.total}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Today&apos;s Calls:</span>
                    <span className="text-white">{apiCallStats.byDate?.[new Date().toISOString().split('T')[0]] || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Most Popular Endpoint:</span>
                    <span className="text-white">
                      {Object.entries(apiCallStats.byEndpoint || {})
                        .sort((a: any, b: any) => b[1] - a[1])
                        .map((entry: any) => entry[0])[0] || 'N/A'}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500">Loading API stats...</p>
              )}
            </div>
          </div>
        )}

        {/* API Usage Tab */}
        {activeTab === 'api' && (
          <div className="p-6 bg-black/30 backdrop-blur-lg border border-white/20 rounded-xl mb-8">
            <h2 className="text-lg font-semibold text-emerald-300 mb-4">API Call Statistics</h2>
            {apiCallStats ? (
              <div>
                <h3 className="text-md font-medium mb-3 text-white/80">By Endpoint</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-white/10">
                    <thead>
                      <tr>
                        <th className="px-4 py-3 text-left text-gray-400 font-medium">Endpoint</th>
                        <th className="px-4 py-3 text-right text-gray-400 font-medium">Calls</th>
                        <th className="px-4 py-3 text-right text-gray-400 font-medium">Percentage</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {Object.entries(apiCallStats.byEndpoint || {})
                        .sort((a: any, b: any) => b[1] - a[1])
                        .map(([endpoint, count]: [string, any]) => (
                          <tr key={endpoint} className="hover:bg-white/5">
                            <td className="px-4 py-3 text-white">/{endpoint}</td>
                            <td className="px-4 py-3 text-right text-white">{count}</td>
                            <td className="px-4 py-3 text-right text-white">
                              {apiCallStats.total ? ((count / apiCallStats.total) * 100).toFixed(1) + '%' : '0%'}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>

                <h3 className="text-md font-medium mb-3 mt-8 text-white/80">By Date</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-white/10">
                    <thead>
                      <tr>
                        <th className="px-4 py-3 text-left text-gray-400 font-medium">Date</th>
                        <th className="px-4 py-3 text-right text-gray-400 font-medium">Calls</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {Object.entries(apiCallStats.byDate || {})
                        .sort((a: any, b: any) => b[0].localeCompare(a[0]))
                        .map(([date, count]: [string, any]) => (
                          <tr key={date} className="hover:bg-white/5">
                            <td className="px-4 py-3 text-white">{date}</td>
                            <td className="px-4 py-3 text-right text-white">{count}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="text-gray-500">Loading API usage data...</p>
            )}
          </div>
        )}

        {/* Error Logs Tab */}
        {activeTab === 'errors' && (
          <div className="p-6 bg-black/30 backdrop-blur-lg border border-white/20 rounded-xl">
            <h2 className="text-lg font-semibold text-emerald-300 mb-4">Error Logs (Last 100 Lines)</h2>
            {errorLogs && errorLogs.length > 0 ? (
              <div className="overflow-x-auto">
                <div className="max-h-[600px] overflow-y-auto p-4 bg-black/50 border border-white/10 rounded-lg text-sm font-mono">
                  {errorLogs.map((log: any, index: number) => (
                    <div key={index} className="mb-2 pb-2 border-b border-white/10 break-words whitespace-pre-wrap text-red-300">
                      {log.message}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-gray-500">No error logs found or still loading...</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
