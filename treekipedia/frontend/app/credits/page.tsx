"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Coins, ArrowUpRight, ArrowDownRight, Loader2, ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCredits } from "@/hooks/useCredits";
import { getCreditTransactions, CreditTransaction } from "@/lib/credits";
import { CreditPurchaseModal } from "@/components/CreditPurchaseModal";

export default function CreditsPage() {
  const { status } = useSession();
  const router = useRouter();
  const { balance, stats, isLoading: balanceLoading, refreshBalance } = useCredits();
  const [transactions, setTransactions] = useState<CreditTransaction[]>([]);
  const [txLoading, setTxLoading] = useState(false);
  const [showPurchase, setShowPurchase] = useState(false);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  // Check for purchase return
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("purchased") === "true") {
      refreshBalance();
      // Clean up URL
      window.history.replaceState({}, "", "/credits");
    }
  }, [refreshBalance]);

  // Fetch transactions
  useEffect(() => {
    if (status !== "authenticated") return;
    setTxLoading(true);
    getCreditTransactions(50, 0)
      .then((data) => setTransactions(data.transactions))
      .catch(console.error)
      .finally(() => setTxLoading(false));
  }, [status]);

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-white/50" />
      </div>
    );
  }

  if (status !== "authenticated") return null;

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const typeLabel: Record<string, string> = {
    purchase: "Credit Purchase",
    signup_bonus: "Signup Bonus",
    site_analysis: "Site Analysis",
    guide: "Guide Synthesis",
    species_research: "Species Research",
    refund: "Refund",
    admin_grant: "Admin Grant",
  };

  return (
    <div className="min-h-screen py-8">
      <div className="max-w-3xl mx-auto px-4 space-y-6">
        {/* Balance Card */}
        <div className="rounded-2xl bg-black/40 backdrop-blur-md border border-white/15 p-6">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-semibold text-white">Credits</h1>
            <Button
              onClick={() => setShowPurchase(true)}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <ShoppingCart className="h-4 w-4 mr-2" />
              Buy Credits
            </Button>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <div className="text-sm text-white/50 mb-1">Balance</div>
              <div className="text-2xl font-semibold text-white flex items-center gap-2">
                <Coins className="h-5 w-5 text-amber-400" />
                {balanceLoading ? "..." : (balance ?? 0).toLocaleString()}
              </div>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <div className="text-sm text-white/50 mb-1">Total Earned</div>
              <div className="text-lg font-medium text-emerald-400">
                {stats ? stats.lifetime_purchased.toLocaleString() : "..."}
              </div>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <div className="text-sm text-white/50 mb-1">Total Spent</div>
              <div className="text-lg font-medium text-white/70">
                {stats ? stats.lifetime_spent.toLocaleString() : "..."}
              </div>
            </div>
          </div>
        </div>

        {/* Transaction History */}
        <div className="rounded-2xl bg-black/40 backdrop-blur-md border border-white/15 p-6">
          <h2 className="text-lg font-medium text-white mb-4">Transaction History</h2>

          {txLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-white/50" />
            </div>
          ) : transactions.length === 0 ? (
            <p className="text-center text-white/40 py-8">No transactions yet</p>
          ) : (
            <div className="space-y-2">
              {transactions.map((tx) => (
                <div
                  key={tx.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/[0.07] transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {tx.amount > 0 ? (
                      <ArrowUpRight className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <ArrowDownRight className="h-4 w-4 text-white/40" />
                    )}
                    <div>
                      <div className="text-sm text-white">
                        {typeLabel[tx.type] || tx.type}
                      </div>
                      <div className="text-xs text-white/40">
                        {formatDate(tx.created_at)}
                      </div>
                    </div>
                  </div>
                  <div
                    className={`font-medium text-sm ${
                      tx.amount > 0 ? "text-emerald-400" : "text-white/60"
                    }`}
                  >
                    {tx.amount > 0 ? "+" : ""}
                    {tx.amount}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <CreditPurchaseModal
        isOpen={showPurchase}
        onClose={() => setShowPurchase(false)}
      />
    </div>
  );
}
