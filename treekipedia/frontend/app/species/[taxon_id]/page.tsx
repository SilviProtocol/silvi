"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { ArrowLeft, Loader2, Sparkles, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SpeciesHeader } from "./components/SpeciesHeader";
import { TabContainer } from "./components/TabContainer";
import { ImageCarousel } from "./components/ImageCarousel";
import { ResearchMetadataPanel } from "./components/ResearchMetadataPanel";
import { useSpeciesData } from "./hooks/useSpeciesData";
import { triggerResearch } from "@/lib/api";
import { useCredits } from "@/hooks/useCredits";
import { CreditGate } from "@/components/CreditGate";

export default function SpeciesDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const taxonId = params.taxon_id as string;
  const [activeTab, setActiveTab] = useState("overview");
  const { status } = useSession();
  const { balance, refreshBalance } = useCredits();
  const [isResearching, setIsResearching] = useState(false);
  const [researchMessage, setResearchMessage] = useState<string | null>(null);
  const [researchMessageType, setResearchMessageType] = useState<'success' | 'info' | 'error'>('info');
  const [showResearchGate, setShowResearchGate] = useState(false);

  // taxonId from URL parameter

  // Use our custom hook that handles data fetching and merging
  const {
    species,
    researchData,
    insightsMetadata,
    hasInsights,
    isLoading,
    isInsightsLoading,
    isError,
    isResearched,
    getFieldValue,
    getInsightForField,
    getInsightsForField, // NEW: Atomic insights support
    isFieldResearched,
    refetchSpecies,
    refetchResearch,
    refetchInsights,
  } = useSpeciesData(taxonId);

  // Show credit gate or redirect to login
  const initiateResearch = (force: boolean = false) => {
    if (status !== 'authenticated') {
      router.push('/login');
      return;
    }
    setShowResearchGate(true);
  };

  // Actually perform research after credit gate confirmation
  const handleResearch = async (force: boolean = false) => {
    setShowResearchGate(false);
    setIsResearching(true);
    setResearchMessage(null);
    setResearchMessageType('info');

    try {
      const result = await triggerResearch(taxonId, force);

      if (result.success) {
        if (result.queued) {
          setResearchMessage(result.message || 'Added to research queue');
          setResearchMessageType('info');
        } else {
          await Promise.all([refetchSpecies(), refetchResearch(), refetchInsights()]);
          setResearchMessage(result.message || `Research synced! ${result.insights_count || 0} insights loaded.`);
          setResearchMessageType('success');
        }
        refreshBalance();
      } else {
        setResearchMessage(result.error || result.message || 'Research failed');
        setResearchMessageType('error');
      }
    } catch (err: any) {
      if (err?.response?.status === 402) {
        setResearchMessage('Insufficient credits');
      } else {
        setResearchMessage(err instanceof Error ? err.message : 'Research failed');
      }
      setResearchMessageType('error');
    } finally {
      setIsResearching(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen">
        <div className="container mx-auto px-4 py-16 flex justify-center items-center">
          <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-5 w-full max-w-2xl">
            <div className="flex items-center justify-center mb-6">
              <Loader2 className="w-10 h-10 animate-spin text-emerald-300" />
            </div>
            <div className="animate-pulse">
              <div className="h-8 bg-white/20 rounded-xl w-1/3 mb-6"></div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {[...Array(6)].map((_, i) => (
                  <div
                    key={i}
                    className="h-4 bg-white/20 rounded-xl w-3/4"
                  ></div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="min-h-screen">
        <div className="container mx-auto px-4 py-16 flex justify-center items-center">
          <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-5 w-full max-w-2xl text-center text-white">
            <div className="flex flex-col">
              <div className="flex items-center justify-center mb-3">
                <div className="text-5xl mr-3">❌</div>
                <h3 className="text-xl font-bold text-emerald-300">Error Loading Species Data</h3>
              </div>
              <p className="text-white text-lg leading-relaxed mb-6">
                Sorry, we encountered an error while trying to load this species. Please try again later.
              </p>
              <Button
                onClick={() => router.push("/search")}
                className="inline-flex px-6 py-3 bg-emerald-600/80 hover:bg-emerald-600 backdrop-blur-md rounded-xl text-white font-semibold transition-colors"
              >
                Return to Search
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Not found state
  if (!species) {
    return (
      <div className="min-h-screen">
        <div className="container mx-auto px-4 py-16 flex justify-center items-center">
          <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-5 w-full max-w-2xl text-center text-white">
            <div className="flex flex-col">
              <div className="flex items-center justify-center mb-3">
                <div className="text-5xl mr-3">🔍</div>
                <h3 className="text-xl font-bold text-emerald-300">Species Not Found</h3>
              </div>
              <p className="text-white text-lg leading-relaxed mb-6">
                We couldn't find information about this species. It may not exist in our database.
              </p>
              <Button
                onClick={() => router.push("/search")}
                className="inline-flex px-6 py-3 bg-emerald-600/80 hover:bg-emerald-600 backdrop-blur-md rounded-xl text-white font-semibold transition-colors"
              >
                Return to Search
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8">
      <div className="max-w-7xl w-full mx-auto px-4">
        {/* Back Button + Research Button */}
        <div className="mb-6 flex items-center gap-3">
          <Button
            onClick={() => router.push("/search")}
            variant="outline"
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-black/40 backdrop-blur-md border border-white/15 text-white hover:bg-black/60 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Search
          </Button>

          {/* Research Button - "Research" for new species */}
          {!hasInsights && (
            <Button
              onClick={() => initiateResearch(false)}
              disabled={isResearching}
              className="flex items-center gap-2 px-4 py-2 rounded-xl backdrop-blur-md text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-emerald-600/80 hover:bg-emerald-600 border border-emerald-400/30"
            >
              {isResearching ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Research (25 credits)
                </>
              )}
            </Button>
          )}

          {/* Re-research Button - for species with existing insights */}
          {hasInsights && (
            <Button
              onClick={() => initiateResearch(true)}
              disabled={isResearching}
              className="flex items-center gap-2 px-4 py-2 rounded-xl backdrop-blur-md text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-emerald-600/60 hover:bg-emerald-600/80 border border-emerald-400/30"
            >
              {isResearching ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" />
                  Re-research (25 credits)
                </>
              )}
            </Button>
          )}

          {researchMessage && (
            <span className={`text-sm ${
              researchMessageType === 'error' ? 'text-red-400' :
              researchMessageType === 'success' ? 'text-emerald-400' :
              'text-amber-300'
            }`}>
              {researchMessage}
            </span>
          )}
        </div>

        {/* Credit Gate for Research */}
        {showResearchGate && (
          <div className="mb-4">
            <CreditGate
              cost={25}
              productLabel="Species Research"
              balance={balance}
              onConfirm={() => handleResearch(hasInsights)}
              onCancel={() => setShowResearchGate(false)}
              isLoading={isResearching}
            />
          </div>
        )}

        {/* Two-column layout: Content + Sidebar (when sidebar has content) */}
        {(() => {
          const hasSidebar = hasInsights || (species.image_count && species.image_count > 0);
          return (
            <div className={`grid grid-cols-1 ${hasSidebar ? 'lg:grid-cols-[1fr,400px]' : ''} gap-6`}>
              {/* Main Content Column */}
              <div className="space-y-4">
                <div className="rounded-xl bg-black/40 backdrop-blur-md border border-white/15 p-4 text-white">
                  <SpeciesHeader species={species} />

                  {/* Tab Navigation */}
                  <TabContainer
                    activeTab={activeTab}
                    setActiveTab={setActiveTab}
                    species={species}
                    researchData={researchData}
                    isResearched={isResearched}
                    getFieldValue={getFieldValue}
                    getInsightForField={getInsightForField}
                    getInsightsForField={getInsightsForField}
                  />
                </div>
              </div>

              {/* Sidebar - sticky on desktop, only rendered when there's content */}
              {hasSidebar && (
                <div className="lg:sticky lg:top-6 lg:self-start space-y-4">
                  {hasInsights && (
                    <ResearchMetadataPanel
                      metadata={insightsMetadata}
                      isLoading={isInsightsLoading}
                    />
                  )}
                  <ImageCarousel taxonId={taxonId} />
                </div>
              )}
            </div>
          );
        })()}
      </div>
    </div>
  );
}