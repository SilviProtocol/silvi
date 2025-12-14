import React from "react";

interface ConservationStatusProps {
  status: string;
  source: "human" | "ai" | "legacy" | null;
}

export function ConservationStatus({ status, source }: ConservationStatusProps) {
  // Get the appropriate styling for the conservation status
  const getStatusStyling = (status: string) => {
    const statusLower = status.toLowerCase();
    
    if (statusLower.includes("extinct") || statusLower.includes("critically endangered")) {
      return "border-red-500 bg-red-900/30";
    } else if (statusLower.includes("endangered")) {
      return "border-orange-500 bg-orange-900/30";
    } else if (statusLower.includes("vulnerable")) {
      return "border-yellow-500 bg-yellow-900/30";
    } else if (statusLower.includes("near threatened")) {
      return "border-yellow-300 bg-yellow-700/30";
    } else if (statusLower.includes("concern") || statusLower.includes("least concern")) {
      return "border-green-500 bg-green-900/30";
    } else {
      return "border-gray-500 bg-gray-900/30";
    }
  };

  return (
    <div className={`p-4 rounded-xl border ${getStatusStyling(status)}`}>
      <div className="text-center">
        <p className="font-bold text-lg mb-1 text-white">{status}</p>
        <p className="text-sm text-white/60">
          {source === "human" ? (
            "Based on human-verified data"
          ) : source === "ai" ? (
            "Based on AI research"
          ) : (
            "Conservation status"
          )}
        </p>
      </div>
    </div>
  );
}