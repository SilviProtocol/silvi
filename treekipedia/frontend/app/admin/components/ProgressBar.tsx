'use client';

import { CheckCircle, Loader2, XCircle } from 'lucide-react';

interface ProgressBarProps {
  progress: number; // 0-100
  status: 'idle' | 'running' | 'complete' | 'error';
  message?: string;
  className?: string;
}

export default function ProgressBar({ progress, status, message, className = '' }: ProgressBarProps) {
  const getStatusColor = () => {
    switch (status) {
      case 'complete':
        return 'bg-emerald-500';
      case 'error':
        return 'bg-red-500';
      case 'running':
        return 'bg-blue-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'complete':
        return <CheckCircle className="w-5 h-5 text-emerald-400" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-400" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
      default:
        return null;
    }
  };

  return (
    <div className={`${className}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          {message && (
            <span className="text-sm text-gray-300">{message}</span>
          )}
        </div>
        <span className="text-sm font-medium text-emerald-300">
          {progress.toFixed(1)}%
        </span>
      </div>

      <div className="w-full h-2 bg-black/30 rounded-full overflow-hidden border border-white/10">
        <div
          className={`h-full ${getStatusColor()} transition-all duration-300 ease-out`}
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        >
          {status === 'running' && (
            <div className="w-full h-full bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
          )}
        </div>
      </div>
    </div>
  );
}
