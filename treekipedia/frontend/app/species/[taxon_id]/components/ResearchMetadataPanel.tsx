import React, { useState } from "react";
import { ChevronDown, ChevronUp, FlaskConical, Calendar, Database, BarChart3, Link2, Cpu } from "lucide-react";

export interface ResearchMetadata {
  version: number;
  research_date: string | null;
  model: string | null;
  confidence: number | null;
  source_count: number;
  fields_filled?: number;
  fields_total?: number;
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

  if (!metadata || metadata.version === 0) {
    return null;
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "Unknown";
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

  const confidence = metadata.confidence ?? 0;
  const confidenceColor = confidence >= 0.85
    ? "text-emerald-400"
    : confidence >= 0.7
      ? "text-amber-400"
      : "text-red-400";

  const confidenceLabel = confidence >= 0.85
    ? "High"
    : confidence >= 0.7
      ? "Medium"
      : "Low";

  return (
    <div className="rounded-xl bg-violet-900/20 border border-violet-500/30 overflow-hidden mb-4">
      {/* Header - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-violet-900/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-violet-400" />
          <span className="font-medium text-violet-300">AI Research</span>
          <span className="text-xs text-white/50">v{metadata.version}</span>
        </div>
        <div className="flex items-center gap-3">
          {confidence > 0 && (
            <span className={`text-sm font-medium ${confidenceColor}`}>
              {Math.round(confidence * 100)}% confidence
            </span>
          )}
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

            {/* Fields Filled */}
            {metadata.fields_filled !== undefined && (
              <div className="flex items-start gap-2">
                <Database className="w-4 h-4 text-violet-400 mt-0.5" />
                <div>
                  <div className="text-xs text-white/50">Fields Populated</div>
                  <div className="text-sm text-white/80">
                    {metadata.fields_filled}/{metadata.fields_total || 25} fields
                  </div>
                </div>
              </div>
            )}

            {/* Sources */}
            <div className="flex items-start gap-2">
              <Link2 className="w-4 h-4 text-violet-400 mt-0.5" />
              <div>
                <div className="text-xs text-white/50">Sources Used</div>
                <div className="text-sm text-white/80">{metadata.source_count} sources</div>
              </div>
            </div>

            {/* Confidence */}
            {confidence > 0 && (
              <div className="flex items-start gap-2">
                <BarChart3 className="w-4 h-4 text-violet-400 mt-0.5" />
                <div>
                  <div className="text-xs text-white/50">Confidence Score</div>
                  <div className={`text-sm font-medium ${confidenceColor}`}>
                    {Math.round(confidence * 100)}% ({confidenceLabel})
                  </div>
                </div>
              </div>
            )}

            {/* Model */}
            {metadata.model && (
              <div className="flex items-start gap-2">
                <Cpu className="w-4 h-4 text-violet-400 mt-0.5" />
                <div>
                  <div className="text-xs text-white/50">Research Model</div>
                  <div className="text-sm text-white/80">{metadata.model}</div>
                </div>
              </div>
            )}

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
          {confidence > 0 && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-xs text-white/50 mb-1">
                <span>Confidence Level</span>
                <span>{Math.round(confidence * 100)}%</span>
              </div>
              <div className="h-2 bg-black/40 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    confidence >= 0.85
                      ? "bg-emerald-500"
                      : confidence >= 0.7
                        ? "bg-amber-500"
                        : "bg-red-500"
                  }`}
                  style={{ width: `${confidence * 100}%` }}
                />
              </div>
            </div>
          )}

          <p className="mt-4 text-xs text-white/40">
            This data was synthesized using AI-assisted research with web search.
            Higher confidence indicates more complete data with multiple source corroboration.
          </p>
        </div>
      )}
    </div>
  );
}
