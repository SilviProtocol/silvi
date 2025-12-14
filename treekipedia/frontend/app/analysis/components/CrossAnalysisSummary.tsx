'use client';

import { CrossAnalysisData } from '@/lib/types';

interface CrossAnalysisSummaryProps {
  crossAnalysis: CrossAnalysisData;
  totalSpecies: number;
}

export default function CrossAnalysisSummary({ crossAnalysis, totalSpecies }: CrossAnalysisSummaryProps) {
  // Calculate percentages
  const calculatePercentage = (count: number) => {
    return totalSpecies > 0 ? Math.round((count / totalSpecies) * 100) : 0;
  };

  const nativePercent = calculatePercentage(crossAnalysis.nativeSpecies);
  const introducedPercent = calculatePercentage(crossAnalysis.introducedSpecies);
  const unknownNativePercent = calculatePercentage(crossAnalysis.unknownNativeStatus);

  const forestPercent = calculatePercentage(crossAnalysis.intactForestSpecies);
  const nonForestPercent = calculatePercentage(crossAnalysis.nonIntactForestSpecies);
  const unknownForestPercent = calculatePercentage(crossAnalysis.unknownForestStatus);

  const commercialPercent = calculatePercentage(crossAnalysis.commercialSpecies);

  return (
    <div className="mb-6 rounded-xl bg-black/30 backdrop-blur-md border border-emerald-600/30 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-emerald-300">
          Cross-Analysis Summary
        </h3>
        {crossAnalysis.dataSource && (
          <span className="text-xs text-white/50 bg-black/30 px-2 py-1 rounded">
            {crossAnalysis.dataSource}
          </span>
        )}
      </div>

      <div className="space-y-4">
        {/* Native Status Section */}
        <div className="bg-blue-900/20 border border-blue-600/30 rounded-lg p-4">
          <h4 className="text-blue-300 font-semibold mb-3 flex items-center">
            <span className="mr-2">🏠</span>
            Native Status
          </h4>
          <div className="grid grid-cols-3 gap-4 text-sm mb-3">
            <div className="text-center">
              <div className="text-lg font-bold text-green-400">{nativePercent}%</div>
              <div className="text-xs text-white/70">Native ({crossAnalysis.nativeSpecies})</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-orange-400">{introducedPercent}%</div>
              <div className="text-xs text-white/70">Introduced ({crossAnalysis.introducedSpecies})</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-gray-400">{unknownNativePercent}%</div>
              <div className="text-xs text-white/70">Unknown ({crossAnalysis.unknownNativeStatus})</div>
            </div>
          </div>
          <div className="bg-black/40 rounded-full h-2 overflow-hidden">
            <div className="flex h-full">
              <div className="bg-green-500" style={{ width: `${nativePercent}%` }}></div>
              <div className="bg-orange-500" style={{ width: `${introducedPercent}%` }}></div>
              <div className="bg-gray-500" style={{ width: `${unknownNativePercent}%` }}></div>
            </div>
          </div>
        </div>

        {/* Intact Forest Card */}
        <div className="bg-green-900/20 border border-green-600/30 rounded-lg p-4">
          <h4 className="text-green-300 font-semibold mb-3 flex items-center">
            <span className="mr-2">🌲</span>
            Intact Forests
          </h4>
          <div className="grid grid-cols-3 gap-4 text-sm mb-3">
            <div className="text-center">
              <div className="text-lg font-bold text-green-400">{forestPercent}%</div>
              <div className="text-xs text-white/70">Present ({crossAnalysis.intactForestSpecies})</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-red-400">{nonForestPercent}%</div>
              <div className="text-xs text-white/70">Absent ({crossAnalysis.nonIntactForestSpecies})</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-gray-400">{unknownForestPercent}%</div>
              <div className="text-xs text-white/70">Unknown ({crossAnalysis.unknownForestStatus})</div>
            </div>
          </div>
          <div className="bg-black/40 rounded-full h-2 overflow-hidden">
            <div className="flex h-full">
              <div className="bg-green-500" style={{ width: `${forestPercent}%` }}></div>
              <div className="bg-red-500" style={{ width: `${nonForestPercent}%` }}></div>
              <div className="bg-gray-500" style={{ width: `${unknownForestPercent}%` }}></div>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}