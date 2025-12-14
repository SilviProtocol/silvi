'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

// Simple client-side password - CHANGE THIS to secure your admin page
const ADMIN_PASSWORD = 'onetwotree'

// Admin page with simple password protection
export default function AdminPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [password, setPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [serverStats, setServerStats] = useState<any>(null)
  const [apiCallStats, setApiCallStats] = useState<any>(null)
  const [errorLogs, setErrorLogs] = useState<any>([])
  const [activeTab, setActiveTab] = useState('stats')
  const [loading, setLoading] = useState(false)

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth'

  // Check if user is already logged in (from localStorage)
  useEffect(() => {
    const isLoggedIn = localStorage.getItem('admin_authenticated') === 'true'
    setIsAuthenticated(isLoggedIn)
  }, [])

  const handleLogin = () => {
    if (password === ADMIN_PASSWORD) {
      setIsAuthenticated(true)
      localStorage.setItem('admin_authenticated', 'true')
      setPasswordError('')
    } else {
      setPasswordError('Incorrect password')
    }
  }

  const handleLogout = () => {
    setIsAuthenticated(false)
    localStorage.removeItem('admin_authenticated')
  }

  // Fetch data from backend API (no auth required on backend anymore)
  const fetchData = async () => {
    setLoading(true)
    try {
      // Fetch server stats and API call stats in parallel
      const [statsRes, callStatsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/admin-api/stats`),
        fetch(`${API_BASE_URL}/admin-api/call-stats`)
      ])

      // Process server stats
      if (statsRes.ok) {
        const statsData = await statsRes.json()
        setServerStats(statsData)
      } else {
        console.error('Failed to fetch server stats:', statsRes.status)
      }

      // Process API call stats
      if (callStatsRes.ok) {
        const callStatsData = await callStatsRes.json()
        setApiCallStats(callStatsData)
      } else {
        console.error('Failed to fetch API call stats:', callStatsRes.status)
      }

      // Only fetch error logs when the errors tab is active
      if (activeTab === 'errors') {
        const logsRes = await fetch(`${API_BASE_URL}/admin-api/errors?limit=100`)
        if (logsRes.ok) {
          const logsData = await logsRes.json()
          setErrorLogs(logsData.logs || [])
        } else {
          console.error('Failed to fetch error logs:', logsRes.status)
        }
      }
    } catch (error) {
      console.error('Error fetching admin data:', error)
    } finally {
      setLoading(false)
    }
  }

  // Load data when authenticated or when tab changes
  useEffect(() => {
    if (isAuthenticated) {
      fetchData()
      // Refresh data every 30 seconds
      const interval = setInterval(fetchData, 30000)
      return () => clearInterval(interval)
    }
  }, [isAuthenticated, activeTab])

  // Format memory sizes
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  // Format server uptime
  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / (3600 * 24))
    const hours = Math.floor((seconds % (3600 * 24)) / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return `${days}d ${hours}h ${mins}m`
  }

  // Render login screen if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4 bg-black bg-opacity-90">
        <Card className="w-full max-w-md p-6 bg-black/50 backdrop-blur-lg border border-white/20 rounded-lg shadow-lg">
          <h1 className="text-2xl font-bold text-white mb-6">Admin Dashboard</h1>
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
                className="w-full p-2 bg-black/30 border border-white/20 rounded-md text-white"
                placeholder="Enter admin password"
              />
              {passwordError && (
                <p className="text-red-500 text-sm mt-1">{passwordError}</p>
              )}
            </div>
            <Button
              onClick={handleLogin}
              className="w-full bg-green-600/80 hover:bg-green-600"
            >
              Login
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  // Render dashboard for authenticated users
  return (
    <div className="min-h-screen p-4 bg-black bg-opacity-90 text-white">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Treekipedia Admin Dashboard</h1>
          <Button 
            onClick={handleLogout}
            className="bg-red-600/70 hover:bg-red-600"
          >
            Logout
          </Button>
        </div>

        {/* Tab Navigation */}
        <div className="mb-6 flex space-x-2 border-b border-white/20">
          <button
            className={`px-4 py-2 ${activeTab === 'stats' ? 'border-b-2 border-green-500 text-green-500' : 'text-white/70'}`}
            onClick={() => setActiveTab('stats')}
          >
            Server Stats
          </button>
          <button
            className={`px-4 py-2 ${activeTab === 'api' ? 'border-b-2 border-green-500 text-green-500' : 'text-white/70'}`}
            onClick={() => setActiveTab('api')}
          >
            API Usage
          </button>
          <button
            className={`px-4 py-2 ${activeTab === 'errors' ? 'border-b-2 border-green-500 text-green-500' : 'text-white/70'}`}
            onClick={() => setActiveTab('errors')}
          >
            Error Logs
          </button>
        </div>

        {/* Refresh button */}
        <div className="mb-4 flex justify-end">
          <Button
            onClick={fetchData}
            disabled={loading}
            className="bg-slate-700/50 hover:bg-slate-700 text-sm"
          >
            {loading ? 'Refreshing...' : 'Refresh Data'}
          </Button>
        </div>

        {/* Stats Tab */}
        {activeTab === 'stats' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <Card className="p-4 bg-black/30 backdrop-blur-lg border border-white/20 rounded-lg">
              <h2 className="text-lg font-semibold mb-3">Server Information</h2>
              {serverStats ? (
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-white/70">Uptime:</span>
                    <span>{formatUptime(serverStats.serverUptime)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Memory (RSS):</span>
                    <span>{formatBytes(serverStats.memoryUsage?.rss || 0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Memory (Heap):</span>
                    <span>{formatBytes(serverStats.memoryUsage?.heapUsed || 0)} / {formatBytes(serverStats.memoryUsage?.heapTotal || 0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Last Updated:</span>
                    <span>{new Date(serverStats.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>
              ) : (
                <p className="text-white/50">Loading server stats...</p>
              )}
            </Card>

            <Card className="p-4 bg-black/30 backdrop-blur-lg border border-white/20 rounded-lg">
              <h2 className="text-lg font-semibold mb-3">API Summary</h2>
              {apiCallStats ? (
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-white/70">Total API Calls:</span>
                    <span>{apiCallStats.total}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Today's Calls:</span>
                    <span>{apiCallStats.byDate?.[new Date().toISOString().split('T')[0]] || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/70">Most Popular Endpoint:</span>
                    <span>
                      {Object.entries(apiCallStats.byEndpoint || {})
                        .sort((a: any, b: any) => b[1] - a[1])
                        .map((entry: any) => entry[0])[0] || 'N/A'}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-white/50">Loading API stats...</p>
              )}
            </Card>
          </div>
        )}

        {/* API Usage Tab */}
        {activeTab === 'api' && (
          <Card className="p-4 bg-black/30 backdrop-blur-lg border border-white/20 rounded-lg mb-8">
            <h2 className="text-lg font-semibold mb-3">API Call Statistics</h2>
            {apiCallStats ? (
              <div>
                <h3 className="text-md font-medium mb-2 text-white/80">By Endpoint</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-white/10">
                    <thead>
                      <tr>
                        <th className="px-4 py-2 text-left text-white/70">Endpoint</th>
                        <th className="px-4 py-2 text-right text-white/70">Calls</th>
                        <th className="px-4 py-2 text-right text-white/70">Percentage</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {Object.entries(apiCallStats.byEndpoint || {})
                        .sort((a: any, b: any) => b[1] - a[1])
                        .map(([endpoint, count]: [string, any]) => (
                          <tr key={endpoint}>
                            <td className="px-4 py-2 text-white/90">/{endpoint}</td>
                            <td className="px-4 py-2 text-right text-white/90">{count}</td>
                            <td className="px-4 py-2 text-right text-white/90">
                              {apiCallStats.total ? ((count / apiCallStats.total) * 100).toFixed(1) + '%' : '0%'}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>

                <h3 className="text-md font-medium mb-2 mt-6 text-white/80">By Date</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-white/10">
                    <thead>
                      <tr>
                        <th className="px-4 py-2 text-left text-white/70">Date</th>
                        <th className="px-4 py-2 text-right text-white/70">Calls</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {Object.entries(apiCallStats.byDate || {})
                        .sort((a: any, b: any) => b[0].localeCompare(a[0]))
                        .map(([date, count]: [string, any]) => (
                          <tr key={date}>
                            <td className="px-4 py-2 text-white/90">{date}</td>
                            <td className="px-4 py-2 text-right text-white/90">{count}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="text-white/50">Loading API usage data...</p>
            )}
          </Card>
        )}

        {/* Error Logs Tab */}
        {activeTab === 'errors' && (
          <Card className="p-4 bg-black/30 backdrop-blur-lg border border-white/20 rounded-lg">
            <h2 className="text-lg font-semibold mb-3">Error Logs (Last 100 Lines)</h2>
            {errorLogs && errorLogs.length > 0 ? (
              <div className="overflow-x-auto">
                <div className="max-h-[600px] overflow-y-auto p-3 bg-black/50 border border-white/10 rounded text-sm font-mono">
                  {errorLogs.map((log: any, index: number) => (
                    <div key={index} className="mb-2 pb-2 border-b border-white/10 break-words whitespace-pre-wrap">
                      {log.message}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-white/50">No error logs found or still loading...</p>
            )}
          </Card>
        )}
      </div>
    </div>
  )
}