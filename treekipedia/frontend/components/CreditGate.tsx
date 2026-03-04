"use client";

import { useState } from "react";
import { Coins, AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CreditPurchaseModal } from "./CreditPurchaseModal";

interface CreditGateProps {
  cost: number;
  productLabel: string;
  balance: number | null;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function CreditGate({ cost, productLabel, balance, onConfirm, onCancel, isLoading }: CreditGateProps) {
  const [showPurchase, setShowPurchase] = useState(false);
  const hasEnough = balance !== null && balance >= cost;

  return (
    <>
      <div className="rounded-xl bg-black/60 backdrop-blur-md border border-white/15 p-5 space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-500/10">
            <Coins className="h-5 w-5 text-amber-400" />
          </div>
          <div>
            <h3 className="text-white font-medium">
              {productLabel}: {cost} credits
            </h3>
            <p className="text-sm text-white/50">
              Your balance: {balance ?? 0} credits
            </p>
          </div>
        </div>

        {!hasEnough && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
            <AlertTriangle className="h-4 w-4 text-red-400 shrink-0" />
            <span className="text-sm text-red-300">
              Insufficient credits. You need {cost - (balance ?? 0)} more.
            </span>
          </div>
        )}

        <div className="flex gap-3">
          {hasEnough ? (
            <>
              <Button
                onClick={onConfirm}
                disabled={isLoading}
                className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {isLoading ? (
                  <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Processing...</>
                ) : (
                  `Confirm (${cost} credits)`
                )}
              </Button>
              <Button
                onClick={onCancel}
                variant="outline"
                className="border-white/15 text-white hover:bg-white/5"
              >
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button
                onClick={() => setShowPurchase(true)}
                className="flex-1 bg-amber-600 hover:bg-amber-700 text-white"
              >
                Buy Credits
              </Button>
              <Button
                onClick={onCancel}
                variant="outline"
                className="border-white/15 text-white hover:bg-white/5"
              >
                Cancel
              </Button>
            </>
          )}
        </div>
      </div>

      <CreditPurchaseModal
        isOpen={showPurchase}
        onClose={() => setShowPurchase(false)}
      />
    </>
  );
}
