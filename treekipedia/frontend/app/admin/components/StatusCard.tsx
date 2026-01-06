'use client';

import { CheckCircle, XCircle, AlertCircle, Loader2 } from 'lucide-react';

export type StatusType = 'connected' | 'disconnected' | 'loading' | 'unknown' | 'healthy' | 'unhealthy';

interface StatusCardProps {
  title: string;
  status: StatusType;
  message?: string;
  details?: Record<string, any>;
  className?: string;
}

const statusConfig = {
  connected: {
    icon: CheckCircle,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
  },
  healthy: {
    icon: CheckCircle,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
  },
  disconnected: {
    icon: XCircle,
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
  },
  unhealthy: {
    icon: XCircle,
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
  },
  loading: {
    icon: Loader2,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
  },
  unknown: {
    icon: AlertCircle,
    color: 'text-gray-400',
    bgColor: 'bg-gray-500/10',
    borderColor: 'border-gray-500/30',
  },
};

export default function StatusCard({ title, status, message, details, className = '' }: StatusCardProps) {
  const config = statusConfig[status] || statusConfig.unknown;
  const Icon = config.icon;

  return (
    <div
      className={`bg-black/30 backdrop-blur-md border ${config.borderColor} rounded-xl p-6 ${className}`}
    >
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-lg font-semibold text-emerald-300">{title}</h3>
        <div className={`flex items-center gap-2 ${config.bgColor} px-3 py-1.5 rounded-lg`}>
          <Icon
            className={`w-4 h-4 ${config.color} ${status === 'loading' ? 'animate-spin' : ''}`}
          />
          <span className={`text-sm font-medium ${config.color} capitalize`}>
            {status}
          </span>
        </div>
      </div>

      {message && (
        <p className="text-sm text-gray-300 mb-3">{message}</p>
      )}

      {details && Object.keys(details).length > 0 && (
        <div className="mt-4 pt-4 border-t border-white/10">
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(details).map(([key, value]) => (
              <div key={key}>
                <p className="text-xs text-gray-400 mb-1">
                  {key.replace(/([A-Z])/g, ' $1').replace(/^./, (str) => str.toUpperCase())}
                </p>
                <p className="text-sm text-white font-mono">
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
