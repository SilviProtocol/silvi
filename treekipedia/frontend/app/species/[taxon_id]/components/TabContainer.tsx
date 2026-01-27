import React from "react";
import { TreeSpecies, ResearchData, Insight } from "@/lib/types";
import { useFieldDefinitions } from "../hooks/useFieldDefinitions";
import { OverviewTab } from "./tabs/OverviewTab";
import { GeographicTab } from "./tabs/GeographicTab";
import { EcologicalTab } from "./tabs/EcologicalTab";
import { PhysicalTab } from "./tabs/PhysicalTab";
import { StewardshipTab } from "./tabs/StewardshipTab";
import { ResearchDataTab } from "./tabs/ResearchDataTab";

interface TabContainerProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  species: TreeSpecies;
  researchData: ResearchData | undefined;
  isResearched: boolean;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  getFieldInsights?: (fieldName: string) => Insight[];
}

export function TabContainer({
  activeTab,
  setActiveTab,
  species,
  researchData,
  isResearched,
  getFieldValue,
}: TabContainerProps) {
  // Get field definitions
  const {
    overviewFields,
    geographicFields,
    ecologicalFields,
    physicalFields,
    stewardshipFields,
    researchDataFields,
  } = useFieldDefinitions();

  return (
    <div>
      {/* Tab Navigation */}
      <div className="flex border-b border-white/15 mb-6 overflow-x-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
        <button
          onClick={() => setActiveTab("overview")}
          className={`px-4 py-2 whitespace-nowrap ${
            activeTab === "overview"
              ? "border-b-2 border-green-400 text-green-400"
              : "text-white/70 hover:text-white"
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab("geographic")}
          className={`px-4 py-2 whitespace-nowrap ${
            activeTab === "geographic"
              ? "border-b-2 border-green-400 text-green-400"
              : "text-white/70 hover:text-white"
          }`}
        >
          Geographic
        </button>
        <button
          onClick={() => setActiveTab("ecological")}
          className={`px-4 py-2 whitespace-nowrap ${
            activeTab === "ecological"
              ? "border-b-2 border-green-400 text-green-400"
              : "text-white/70 hover:text-white"
          }`}
        >
          Ecological
        </button>
        <button
          onClick={() => setActiveTab("physical")}
          className={`px-4 py-2 whitespace-nowrap ${
            activeTab === "physical"
              ? "border-b-2 border-green-400 text-green-400"
              : "text-white/70 hover:text-white"
          }`}
        >
          Physical
        </button>
        <button
          onClick={() => setActiveTab("stewardship")}
          className={`px-4 py-2 whitespace-nowrap ${
            activeTab === "stewardship"
              ? "border-b-2 border-green-400 text-green-400"
              : "text-white/70 hover:text-white"
          }`}
        >
          Stewardship
        </button>
        <button
          onClick={() => setActiveTab("research")}
          className={`px-4 py-2 whitespace-nowrap ${
            activeTab === "research"
              ? "border-b-2 border-green-400 text-green-400"
              : "text-white/70 hover:text-white"
          }`}
        >
          Research Data
        </button>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === "overview" && (
          <OverviewTab
            species={species}
            isResearched={isResearched}
            getFieldValue={getFieldValue}
            fields={overviewFields}
          />
        )}
        
        {activeTab === "geographic" && (
          <GeographicTab
            species={species}
            isResearched={isResearched}
            getFieldValue={getFieldValue}
            fields={geographicFields}
          />
        )}
        
        {activeTab === "ecological" && (
          <EcologicalTab
            species={species}
            isResearched={isResearched}
            getFieldValue={getFieldValue}
            fields={ecologicalFields}
          />
        )}
        
        {activeTab === "physical" && (
          <PhysicalTab
            species={species}
            isResearched={isResearched}
            getFieldValue={getFieldValue}
            fields={physicalFields}
          />
        )}
        
        {activeTab === "stewardship" && (
          <StewardshipTab
            species={species}
            isResearched={isResearched}
            getFieldValue={getFieldValue}
            fields={stewardshipFields}
          />
        )}
        
        {activeTab === "research" && (
          <ResearchDataTab
            species={species}
            isResearched={isResearched}
            getFieldValue={getFieldValue}
            fields={researchDataFields}
          />
        )}
      </div>
    </div>
  );
}