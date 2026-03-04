"use client";

import { useState, useEffect } from "react";
import { X, Loader2, ExternalLink } from "lucide-react";
import { getCreditPacks, createCreditInvoice, CreditPack } from "@/lib/credits";

interface CreditPurchaseModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CreditPurchaseModal({ isOpen, onClose }: CreditPurchaseModalProps) {
  const [packs, setPacks] = useState<CreditPack[]>([]);
  const [loading, setLoading] = useState(false);
  const [purchasing, setPurchasing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      getCreditPacks()
        .then(setPacks)
        .catch(() => setError("Failed to load credit packs"))
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  const handlePurchase = async (packId: string) => {
    setPurchasing(packId);
    setError(null);
    try {
      const { invoice_url } = await createCreditInvoice(packId);
      window.location.href = invoice_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create invoice");
      setPurchasing(null);
    }
  };

  if (!isOpen) return null;

  const perCredit = (pack: CreditPack) =>
    (parseFloat(pack.price_usd) / pack.credits).toFixed(2);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-lg mx-4 rounded-2xl bg-black/80 backdrop-blur-lg border border-white/10 p-6">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-white/50 hover:text-white"
        >
          <X className="h-5 w-5" />
        </button>

        <h2 className="text-xl font-semibold text-white mb-1">Buy Credits</h2>
        <p className="text-sm text-white/60 mb-6">
          Pay with crypto via NOWPayments
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-white/50" />
          </div>
        ) : (
          <div className="space-y-3">
            {packs.map((pack) => (
              <button
                key={pack.id}
                onClick={() => handlePurchase(pack.id)}
                disabled={!!purchasing}
                className="w-full flex items-center justify-between p-4 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-400/30 transition-all disabled:opacity-50"
              >
                <div className="text-left">
                  <div className="text-white font-medium">{pack.name}</div>
                  <div className="text-sm text-white/50">
                    {pack.credits.toLocaleString()} credits &middot; ${perCredit(pack)}/credit
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-emerald-400 font-semibold">
                    ${parseFloat(pack.price_usd).toFixed(0)}
                  </span>
                  {purchasing === pack.id ? (
                    <Loader2 className="h-4 w-4 animate-spin text-white/50" />
                  ) : (
                    <ExternalLink className="h-4 w-4 text-white/30" />
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
