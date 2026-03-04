"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { getCreditBalance, CreditBalance } from "@/lib/credits";

export function useCredits() {
  const { data: session, status } = useSession();
  const [balance, setBalance] = useState<number | null>(null);
  const [stats, setStats] = useState<CreditBalance | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const isAuthenticated = status === "authenticated" && !!session?.user;

  const refreshBalance = useCallback(async () => {
    if (!isAuthenticated) {
      setBalance(null);
      setStats(null);
      return;
    }

    setIsLoading(true);
    try {
      const data = await getCreditBalance();
      setBalance(data.balance);
      setStats(data);
    } catch (err) {
      console.error("Failed to fetch credit balance:", err);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  // Fetch on mount and when auth changes
  useEffect(() => {
    refreshBalance();
  }, [refreshBalance]);

  // Refresh on window focus
  useEffect(() => {
    const onFocus = () => {
      if (isAuthenticated) refreshBalance();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [isAuthenticated, refreshBalance]);

  return { balance, stats, isLoading, refreshBalance, isAuthenticated };
}
