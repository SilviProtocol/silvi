"use client";

import { useCredits } from "@/hooks/useCredits";
import Link from "next/link";
import { Coins } from "lucide-react";

export function CreditBalance() {
  const { balance, isLoading, isAuthenticated } = useCredits();

  if (!isAuthenticated) return null;

  return (
    <Link
      href="/credits"
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-colors text-sm"
    >
      <Coins className="h-4 w-4 text-amber-400" />
      {isLoading ? (
        <span className="text-white/50 w-6 h-4 bg-white/10 animate-pulse rounded" />
      ) : (
        <span className="text-white font-medium">{balance ?? 0}</span>
      )}
    </Link>
  );
}
