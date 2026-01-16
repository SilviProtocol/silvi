import { useState, useCallback, useRef, useEffect } from "react";
import { toast } from "sonner";
import { triggerResearch } from "@/lib/api";
import { TreeSpecies } from "@/lib/types";

// NOTE: NFT minting and blockchain features are disabled (Jan 2026)
// Research now uses queue-based Claude Code CLI workflow
// The old payment/NFT code is preserved in archive/ for future reference

/**
 * Custom hook for managing the research request process
 *
 * NEW WORKFLOW (Jan 2026):
 * 1. User clicks "Research" button
 * 2. Species added to research_queue
 * 3. Claude Code CLI processes queue via scripts/research_species.py
 * 4. Insights saved to database
 * 5. Frontend polls for completion
 */
export function useResearchProcess(
  taxonId: string,
  species: TreeSpecies | undefined,
  _address: string | undefined, // Kept for API compatibility but not used
  refetchSpecies: () => Promise<any>,
  refetchResearch: () => Promise<any>
) {
  const [isResearching, setIsResearching] = useState(false);
  const [researchStatus, setResearchStatus] = useState<
    "idle" | "starting" | "queued" | "processing" | "complete" | "error" | "timeout"
  >("idle");
  const [progressMessage, setProgressMessage] = useState("");
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const messageIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Cycling research messages
  const researchMessages = [
    "Adding to research queue...",
    "Scanning global databases...",
    "Consulting POWO and WCVP...",
    "Checking IUCN Red List...",
    "Exploring GBIF occurrences...",
    "Mining grey literature...",
    "Analyzing ecological data...",
    "Documenting traditional uses...",
    "Compiling research findings...",
    "Verifying source credibility..."
  ];

  // Start the research process
  const startResearch = useCallback(async () => {
    if (!species || isResearching) return;

    setIsResearching(true);
    setResearchStatus("starting");
    setProgressMessage("Adding to research queue...");

    try {
      // Call triggerResearch which adds to queue
      const response = await triggerResearch(taxonId);

      if (response.success) {
        if (response.queued) {
          // Species added to queue
          setResearchStatus("queued");
          setProgressMessage(`Research queued. Status: ${response.queue_status}`);

          if (response.queue_status === 'pending') {
            toast.success("Added to research queue! Research will be processed soon.");
          } else if (response.queue_status === 'processing') {
            toast.info("Research is currently in progress...");
            // Start polling for completion
            startPollingForResearch();
          }

          // Start cycling through messages while waiting
          let messageIndex = 0;
          messageIntervalRef.current = setInterval(() => {
            setProgressMessage(researchMessages[messageIndex % researchMessages.length]);
            messageIndex++;
          }, 3000);

          // Start polling for completion
          startPollingForResearch();
        } else {
          // Research data already exists and was synced
          setResearchStatus("complete");
          toast.success(`Research synced! ${response.insights_count || 0} insights loaded.`);

          // Refetch data
          await Promise.all([refetchSpecies(), refetchResearch()]);
          setIsResearching(false);
        }
      } else {
        throw new Error(response.error || response.message || "Failed to queue research");
      }
    } catch (error: any) {
      setResearchStatus("error");
      console.error("Research error:", error);

      // Clear message interval
      if (messageIntervalRef.current) {
        clearInterval(messageIntervalRef.current);
      }

      toast.error(error.message || "Failed to start research");
      setIsResearching(false);
    }
  }, [taxonId, species, isResearching]);

  // Polling implementation with exponential backoff
  const startPollingForResearch = useCallback(() => {
    let attempts = 0;
    const maxAttempts = 60; // Check for up to 3 minutes (60 * 3s)
    const baseInterval = 3000;

    const pollForData = async () => {
      if (attempts >= maxAttempts) {
        // Clean up message cycling
        if (messageIntervalRef.current) {
          clearInterval(messageIntervalRef.current);
        }

        setResearchStatus("timeout");
        setIsResearching(false);
        // Don't show error - research is queued and will complete later
        toast.info("Research is queued. Check back later for results.");
        return;
      }

      attempts++;
      const backoffFactor = Math.min(2, 1 + attempts / 20);
      const nextInterval = baseInterval * backoffFactor;

      try {
        // Refetch both data sources
        const [speciesResult, researchResult] = await Promise.all([
          refetchSpecies(),
          refetchResearch(),
        ]);

        // Check if research completed
        console.log(`Poll attempt ${attempts}: Checking for research data...`);

        const researchedFlag = speciesResult.data?.researched === true;
        const hasAiData = !!(
          researchResult.data?.general_description_ai ||
          speciesResult.data?.general_description_ai
        );

        if (researchedFlag || hasAiData) {
          // Clean up message cycling
          if (messageIntervalRef.current) {
            clearInterval(messageIntervalRef.current);
          }

          console.log("Research complete - data found!");

          setResearchStatus("complete");
          setIsResearching(false);
          toast.success("Research completed successfully!");

          // Force refetch to ensure UI reflects new data
          setTimeout(() => {
            refetchSpecies();
            refetchResearch();
          }, 1000);

          return;
        }

        // Schedule next poll
        pollIntervalRef.current = setTimeout(pollForData, nextInterval);
      } catch (error) {
        console.error("Polling error:", error);
        // Continue polling despite errors
        pollIntervalRef.current = setTimeout(pollForData, nextInterval);
      }
    };

    // Start polling after initial delay
    pollIntervalRef.current = setTimeout(pollForData, 2000);
  }, [refetchSpecies, refetchResearch]);

  // Clean up polling and message cycling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearTimeout(pollIntervalRef.current);
      }
      if (messageIntervalRef.current) {
        clearInterval(messageIntervalRef.current);
      }
    };
  }, []);

  return {
    isResearching,
    researchStatus,
    progressMessage,
    startResearch,
  };
}
