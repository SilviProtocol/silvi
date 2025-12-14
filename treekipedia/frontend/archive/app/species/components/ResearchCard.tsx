import React from "react";
import { Leaf, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { TreeSpecies } from "@/lib/types";
import { SponsorshipButton } from "@/components/sponsorship-button";

interface ResearchCardProps {
  species: TreeSpecies;
  isResearched: boolean;
  taxonId: string;
  address: string | undefined;
  refetchSpecies: () => Promise<any>;
  refetchResearch: () => Promise<any>;
}

export function ResearchCard({
  species,
  isResearched,
  taxonId,
  address,
  refetchSpecies,
  refetchResearch,
}: ResearchCardProps) {
  const router = useRouter();
  const [isResearching, setIsResearching] = React.useState(false);
  const [progressMessage, setProgressMessage] = React.useState("");
  const [progressPercent, setProgressPercent] = React.useState(33); // Default to 33% for transaction phase
  
  // Handle manual refresh to force UI update
  const forceRefresh = React.useCallback(async () => {
    try {
      console.log("Forcing data refresh...");
      // First fetch species to get the researched flag from the database
      await refetchSpecies();
      console.log("Species data refreshed successfully, checking researched flag");
      // Then fetch research data (but only species.researched flag determines UI state)
      await refetchResearch();
      console.log("Research data refreshed - will rely on species.researched flag for UI state");
    } catch (error) {
      console.error("Error refreshing data:", error);
    }
  }, [refetchSpecies, refetchResearch]);
  
  // Handle sponsorship completion
  const handleSponsorshipComplete = () => {
    forceRefresh();
  };
  
  // Monitor researched status changes and force updates
  React.useEffect(() => {
    // If we were in researching state but isResearched becomes true,
    // make sure we update the UI and stop researching animation
    if (isResearching && isResearched) {
      console.log("Research completed, updating UI state");
      // Set progress to 100% for visual completion
      setProgressPercent(100);
      setProgressMessage("Research complete!");
      
      // Short delay before switching view to show completion animation
      setTimeout(() => {
        setIsResearching(false);
      }, 1500);
    }
  }, [isResearched, isResearching, setProgressPercent, setProgressMessage]);
  
  // Add additional refetch on mount and at intervals to ensure data is fresh
  React.useEffect(() => {
    // Initial fetch on mount
    const fetchData = async () => {
      try {
        // First fetch species data to check the researched flag from DB
        await refetchSpecies();
        // Then fetch research data without modifying any flags
        await refetchResearch();
        console.log("Data refresh completed, will rely on researched flag from species data");
      } catch (error) {
        console.error("Error refreshing data:", error);
      }
    };
    
    // Do initial fetch
    fetchData();
    
    // Set up a periodic refresh ONLY if we're actively researching
    // This fetches fresh data but the UI state only changes when DB flag changes
    let intervalId: NodeJS.Timeout | null = null;
    
    if (isResearching && !isResearched) {
      console.log("Setting up periodic refresh to check for research completion");
      intervalId = setInterval(fetchData, 5000); // Check every 5 seconds
    }
    
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [isResearching, isResearched, refetchSpecies, refetchResearch]);

  return (
    <div className="rounded-xl bg-black/30 backdrop-blur-md border border-white/20 p-6 text-white mb-6 sticky top-4">
      <h2 className="text-xl font-bold mb-4 flex items-center text-emerald-300">
        <Leaf className="w-5 h-5 mr-2" />
        Tree Intelligence Commons
      </h2>

      {isResearched ? (
        <div>
          <div className="p-4 rounded-lg bg-black/30 backdrop-blur-md border border-white/20 mb-4">
            <div className="mb-3 text-xl font-bold text-emerald-300">AI Research Complete</div>
            <p className="text-white text-lg leading-relaxed mb-2">
              This species has been researched with AI. Thank you to all contributors who have
              funded tree intelligence!
            </p>

            {/* Research data statistics would go here */}
          </div>
          <Button
            onClick={() => router.push("/profile")}
            className="w-full bg-emerald-600/80 hover:bg-emerald-600 backdrop-blur-md rounded-xl text-white font-semibold transition-colors"
          >
            View My Contreebutions
          </Button>
        </div>
      ) : (
        <div>
          {isResearching ? (
            <div className="p-4 rounded-lg bg-black/30 backdrop-blur-md border border-emerald-500/40 mb-4">
              <div className="flex justify-between items-center mb-3">
                <span className="text-white text-lg">Research Status:</span>
                <span className="font-bold text-emerald-300">Processing</span>
              </div>
              <div className="flex items-center justify-center gap-3 mb-3">
                <Loader2 className="h-5 w-5 animate-spin text-emerald-400" />
                <span className="text-emerald-300 font-medium">{progressMessage}</span>
              </div>
              <div className="relative pt-1">
                <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-emerald-900/30">
                  <div
                    className="animate-pulse bg-emerald-500 h-full rounded transition-all duration-1000 ease-in-out"
                    style={{ width: `${progressPercent}%` }}
                  ></div>
                </div>
              </div>
              <p className="text-white/70 text-sm">
                This typically takes 20-30 seconds. The page will update automatically when complete.
              </p>
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-black/30 backdrop-blur-md border border-white/20 mb-4">
              <div className="flex justify-between items-center mb-3">
                <span className="text-white text-lg">Fund Research:</span>
                <span className="font-bold text-emerald-300">$3</span>
              </div>
              <div className="space-y-2 text-base text-white/80">
                <p>
                  <span className="inline-block w-5 h-5 text-center mr-2 rounded-full bg-white/10">
                    ✓
                  </span>
                  Unlock AI research for this species
                </p>
                <p>
                  <span className="inline-block w-5 h-5 text-center mr-2 rounded-full bg-white/10">
                    ✓
                  </span>
                  Receive a Contreebution NFT
                </p>
                <p>
                  <span className="inline-block w-5 h-5 text-center mr-2 rounded-full bg-white/10">
                    ✓
                  </span>
                  Earn points on the Treederboard
                </p>
                <p>
                  <span className="inline-block w-5 h-5 text-center mr-2 rounded-full bg-white/10">
                    ✓
                  </span>
                  Help build the tree knowledge commons
                </p>
              </div>
            </div>
          )}

          {/* Use the enhanced SponsorshipButton for direct USDC transfer */}
          <SponsorshipButton
            taxonId={taxonId}
            speciesName={species?.species_scientific_name || species?.species || ''}
            onSponsorshipComplete={handleSponsorshipComplete}
            className="w-full bg-emerald-600/80 hover:bg-emerald-600 backdrop-blur-md rounded-xl text-white font-semibold transition-colors"
            setIsResearching={setIsResearching}
            setProgressMessage={setProgressMessage}
            setProgressPercent={setProgressPercent}
          />
        </div>
      )}

      {/* Research Process Info */}
      <div className="mt-6 pt-6 border-t border-white/10">
        <h3 className="text-xl font-bold mb-3 text-emerald-300">How It Works</h3>
        <div className="space-y-3 text-base">
          <div className="flex items-start gap-2">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-900/50 text-emerald-400 flex items-center justify-center text-xs">
              1
            </div>
            <p className="text-white/80">Fund research for this species.</p>
          </div>
          <div className="flex items-start gap-2">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-900/50 text-emerald-400 flex items-center justify-center text-xs">
              2
            </div>
            <p className="text-white/80">AI research agent collects & structures data.</p>
          </div>
          <div className="flex items-start gap-2">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-900/50 text-emerald-400 flex items-center justify-center text-xs">
              3
            </div>
            <p className="text-white/80">
              Data is stored on IPFS & a Contreebution NFT is minted.
            </p>
          </div>
          <div className="flex items-start gap-2">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-900/50 text-emerald-400 flex items-center justify-center text-xs">
              4
            </div>
            <p className="text-white/80">Knowledge is available for everyone forever.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Using direct USDC transfer approach with two-phase UI
// Phase 1: Transaction - Shows progress bar at 33% with transaction-related messages
// Phase 2: Research - Progress bar fills from 33% to 100% with research-related messages
// This approach uses a direct USDC transfer to a treasury wallet
// The backend monitors these transfers and triggers the research process