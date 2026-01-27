import React from "react";
import { TreeSpecies, Insight } from "@/lib/types";
import { DataField } from "../DataField";
import { FieldDefinition } from "../../hooks/useFieldDefinitions";

interface ResearchDataTabProps {
  species: TreeSpecies;
  isResearched: boolean;
  getFieldValue: (fieldName: string) => { value: any; source: "human" | "ai" | "legacy" | null };
  getFieldInsights?: (fieldName: string) => Insight[];
  fields: FieldDefinition[];
}

export function ResearchDataTab({ species, isResearched, getFieldValue, getFieldInsights, fields }: ResearchDataTabProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-4">Research & Data</h2>

        {/* Research metadata */}
        {isResearched && species.research_version && species.research_version > 0 && (
          <div className="p-4 rounded-lg bg-emerald-900/20 border border-emerald-500/20 mb-4">
            <h3 className="font-semibold text-emerald-300 mb-2">Research Status</h3>
            <p className="text-white/80 mb-2">
              This species has been researched using AI-assisted research with web search.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 text-sm">
              <div>
                <span className="text-white/60">Version: </span>
                <span className="text-white">v{species.research_version}</span>
              </div>
              {species.research_date && (
                <div>
                  <span className="text-white/60">Date: </span>
                  <span className="text-white">
                    {new Date(species.research_date).toLocaleDateString()}
                  </span>
                </div>
              )}
              {species.research_confidence && (
                <div>
                  <span className="text-white/60">Confidence: </span>
                  <span className="text-white">
                    {Math.round(species.research_confidence * 100)}%
                  </span>
                </div>
              )}
              {species.research_agent && (
                <div>
                  <span className="text-white/60">Model: </span>
                  <span className="text-white">{species.research_agent}</span>
                </div>
              )}
            </div>
            {species.ipfs_cid && species.ipfs_cid !== "" && species.ipfs_cid !== "NA" && (
              <div className="mt-4 text-sm">
                <span className="text-white/60">IPFS CID: </span>
                <a
                  href={`https://ipfs.io/ipfs/${species.ipfs_cid}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-emerald-400 hover:text-emerald-300 break-all"
                >
                  {species.ipfs_cid}
                </a>
              </div>
            )}
          </div>
        )}

        {/* Fields display */}
        <div className="space-y-3">
          {fields.map((field) => (
            <DataField
              key={field.key}
              field={field}
              getFieldValue={getFieldValue}
              isResearched={isResearched}
              isFieldResearched={(fieldName) => {
                const { value } = getFieldValue(fieldName);
                return !!value;
              }}
              insights={getFieldInsights?.(field.key)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}