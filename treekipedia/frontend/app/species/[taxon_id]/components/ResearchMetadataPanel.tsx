import React, { useState } from "react";
import { ChevronDown, ChevronUp, FlaskConical, Calendar, Database, BarChart3, Link2, Cpu } from "lucide-react";

export interface ResearchMetadata {
  version: number;
  research_date: string;
  model: string;
  insight_count: number;
  field_count: number;  // Number of unique claim_types (fields)
  avg_confidence: number;
  source_count: number;
  session_id?: string;
}

interface ResearchMetadataPanelProps {
  metadata: ResearchMetadata | null;
  isLoading?: boolean;
}

export function ResearchMetadataPanel({ metadata, isLoading }: ResearchMetadataPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="rounded-xl bg-violet-900/20 border border-violet-500/30 p-4 animate-pulse">
        <div className="h-5 bg-violet-500/20 rounded w-1/3 mb-2"></div>
        <div className="h-4 bg-violet-500/10 rounded w-2/3"></div>
      </div>
    );
  }

  if (!metadata) {
    return null;
  }

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  const confidenceColor = metadata.avg_confidence >= 0.85
    ? "text-emerald-400"
    : metadata.avg_confidence >= 0.7
      ? "text-amber-400"
      : "text-red-400";

  const confidenceLabel = metadata.avg_confidence >= 0.85
    ? "High"
    : metadata.avg_confidence >= 0.7
      ? "Medium"
      : "Low";

  return (
    <div className="rounded-xl bg-violet-900/20 border border-violet-500/30 overflow-hidden">
      {/* Header - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-violet-900/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-violet-400" />
          <span className="font-medium text-violet-300">Synthetic Knowledge</span>
          <span className="text-xs text-white/50">v{metadata.version}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-sm font-medium ${confidenceColor}`}>
            {Math.round(metadata.avg_confidence * 100)}% confidence
          </span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-white/50" />
          ) : (
            <ChevronDown className="w-4 h-4 text-white/50" />
          )}
        </div>
      </button>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-violet-500/20">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {/* Research Date */}
            <div className="flex items-start gap-2">
              <Calendar className="w-4 h-4 text-violet-400 mt-0.5" />
              <div>
                <div className="text-xs text-white/50">Research Date</div>
                <div className="text-sm text-white/80">{formatDate(metadata.research_date)}</div>
              </div>
            </div>

            {/* Insights Count */}
            <div className="flex items-start gap-2">
              <Database className="w-4 h-4 text-violet-400 mt-0.5" />
              <div>
                <div className="text-xs text-white/50">Insights</div>
                <div className="text-sm text-white/80">
                  {metadata.insight_count} insight{metadata.insight_count !== 1 ? 's' : ''}
                  {metadata.field_count && metadata.field_count !== metadata.insight_count && (
                    <span className="text-white/50"> across {metadata.field_count} fields</span>
                  )}
                </div>
              </div>
            </div>

            {/* Sources */}
            <div className="flex items-start gap-2">
              <Link2 className="w-4 h-4 text-violet-400 mt-0.5" />
              <div>
                <div className="text-xs text-white/50">Sources Cited</div>
                <div className="text-sm text-white/80">{metadata.source_count} sources</div>
              </div>
            </div>

            {/* Confidence */}
            <div className="flex items-start gap-2">
              <BarChart3 className="w-4 h-4 text-violet-400 mt-0.5" />
              <div>
                <div className="text-xs text-white/50">Avg Confidence</div>
                <div className={`text-sm font-medium ${confidenceColor}`}>
                  {Math.round(metadata.avg_confidence * 100)}% ({confidenceLabel})
                </div>
              </div>
            </div>

            {/* Model */}
            <div className="flex items-start gap-2">
              <Cpu className="w-4 h-4 text-violet-400 mt-0.5" />
              <div>
                <div className="text-xs text-white/50">Research Model</div>
                <div className="text-sm text-white/80">{metadata.model}</div>
              </div>
            </div>

            {/* Version */}
            <div className="flex items-start gap-2">
              <FlaskConical className="w-4 h-4 text-violet-400 mt-0.5" />
              <div>
                <div className="text-xs text-white/50">Version</div>
                <div className="text-sm text-white/80">v{metadata.version}</div>
              </div>
            </div>
          </div>

          {/* Confidence bar visualization */}
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-white/50 mb-1">
              <span>Confidence Distribution</span>
              <span>{Math.round(metadata.avg_confidence * 100)}%</span>
            </div>
            <div className="h-2 bg-black/40 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  metadata.avg_confidence >= 0.85
                    ? "bg-emerald-500"
                    : metadata.avg_confidence >= 0.7
                      ? "bg-amber-500"
                      : "bg-red-500"
                }`}
                style={{ width: `${metadata.avg_confidence * 100}%` }}
              />
            </div>
          </div>

          <p className="mt-4 text-xs text-white/40">
            This data was synthesized from multiple scientific databases and publications using
            AI-assisted research. Higher confidence indicates stronger source agreement.
          </p>
        </div>
      )}
    </div>
  );
}
