import React, { useState } from "react";
import { ChevronDown, ChevronUp, FlaskConical, Calendar, Database, BarChart3, Link2, Cpu } from "lucide-react";

export interface ResearchMetadata {
  version: number;
  research_date: string;
  model: string;
  insight_count: number;
  field_count: number;
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
      <div className="rounded-xl bg-black/40 backdrop-blur-md border border-emerald-500/25 p-4 animate-pulse">
        <div className="h-5 bg-emerald-500/10 rounded w-1/3 mb-2"></div>
        <div className="h-4 bg-white/5 rounded w-2/3"></div>
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

  // Confidence colors — emerald with opacity scaling
  const getConfidenceOpacity = (conf: number) => {
    if (conf >= 0.90) return "opacity-100";
    if (conf >= 0.80) return "opacity-80";
    if (conf >= 0.70) return "opacity-60";
    return "opacity-40";
  };

  const confidenceColor = `text-emerald-400 ${getConfidenceOpacity(metadata.avg_confidence)}`;
  const confidenceBarColor = `bg-emerald-500 ${getConfidenceOpacity(metadata.avg_confidence)}`;

  const confidenceLabel = metadata.avg_confidence >= 0.85
    ? "High"
    : metadata.avg_confidence >= 0.7
      ? "Good"
      : "Fair";

  return (
    <div className="rounded-xl bg-black/40 backdrop-blur-md border border-emerald-500/25 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-emerald-400" />
          <span className="font-medium text-emerald-300">AI Research</span>
          <span className="text-xs text-white/40">v{metadata.version}</span>
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
        <div className="px-4 pb-4 pt-2 border-t border-white/10">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="flex items-start gap-2">
              <Calendar className="w-4 h-4 text-white/40 mt-0.5" />
              <div>
                <div className="text-xs text-white/40">Research Date</div>
                <div className="text-sm text-white/80">{formatDate(metadata.research_date)}</div>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <Database className="w-4 h-4 text-white/40 mt-0.5" />
              <div>
                <div className="text-xs text-white/40">Insights</div>
                <div className="text-sm text-white/80">
                  {metadata.insight_count} insight{metadata.insight_count !== 1 ? 's' : ''}
                  {metadata.field_count && metadata.field_count !== metadata.insight_count && (
                    <span className="text-white/40"> across {metadata.field_count} fields</span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <Link2 className="w-4 h-4 text-white/40 mt-0.5" />
              <div>
                <div className="text-xs text-white/40">Sources Cited</div>
                <div className="text-sm text-white/80">{metadata.source_count} sources</div>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <BarChart3 className="w-4 h-4 text-white/40 mt-0.5" />
              <div>
                <div className="text-xs text-white/40">Avg Confidence</div>
                <div className={`text-sm font-medium ${confidenceColor}`}>
                  {Math.round(metadata.avg_confidence * 100)}% ({confidenceLabel})
                </div>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <Cpu className="w-4 h-4 text-white/40 mt-0.5" />
              <div>
                <div className="text-xs text-white/40">Research Model</div>
                <div className="text-sm text-white/80">{metadata.model}</div>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <FlaskConical className="w-4 h-4 text-white/40 mt-0.5" />
              <div>
                <div className="text-xs text-white/40">Version</div>
                <div className="text-sm text-white/80">v{metadata.version}</div>
              </div>
            </div>
          </div>

          {/* Confidence bar */}
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-white/40 mb-1">
              <span>Confidence Distribution</span>
              <span>{Math.round(metadata.avg_confidence * 100)}%</span>
            </div>
            <div className="h-2 bg-black/40 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${confidenceBarColor}`}
                style={{ width: `${metadata.avg_confidence * 100}%` }}
              />
            </div>
          </div>

          <p className="mt-4 text-xs text-white/30">
            Synthesized from scientific databases and publications using AI-assisted research.
            Higher confidence indicates stronger source agreement.
          </p>
        </div>
      )}
    </div>
  );
}
