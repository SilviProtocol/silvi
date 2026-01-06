"use client";

import { useState, useEffect } from "react";
import { Navbar } from "@/components/navbar";
import { getTreederboard } from "@/lib/api";
import { Loader2, AlertCircle } from "lucide-react";
import Link from "next/link";
import { formatAddress } from "@/lib/utils";

// Types for Treederboard data
interface TreederboardUser {
  id: number;
  wallet_address: string;
  display_name?: string;
  total_points: number;
  contribution_count: number;
  first_contribution_at?: string;
  last_contribution_at?: string;
}

export default function TreederboardPage() {
  const [leaderboard, setLeaderboard] = useState<TreederboardUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchLeaderboard() {
      try {
        setIsLoading(true);
        setError(null);
        const data = await getTreederboard(50); // Get top 50 users
        setLeaderboard(data);
      } catch (err) {
        console.error("Failed to fetch leaderboard:", err);
        setError("Failed to load the Treederboard. Please try again later.");
      } finally {
        setIsLoading(false);
      }
    }

    fetchLeaderboard();
  }, []);

  return (
    <main className="min-h-screen text-white">
      <Navbar />
      <div className="relative min-h-screen flex flex-col z-10">
        {/* Modern header section */}
        <div className="max-w-6xl mx-auto pt-20 pb-8 px-4 w-full">
          <div className="mb-6 text-center">
            <h1 className="relative inline-block text-4xl font-bold tracking-tighter mb-8">
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-emerald-300 via-green-200 to-teal-300 animate-gradient-x">Treederboard</span>
              <div className="absolute -bottom-2 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-400 to-transparent"></div>
            </h1>
            <div className="mb-2">
              <p className="text-white max-w-3xl mx-auto text-lg leading-relaxed">
                This leaderboard showcases our top contributors. Rankings are based on the points earned for research funding and tree stewardship.
              </p>
            </div>
          </div>
        </div>
        
        {/* Leaderboard section */}
        <div className="flex-1 mx-auto w-full max-w-6xl px-4 mb-6 -mt-2">
          <div className="mb-2">
            <h2 className="text-xl font-bold text-emerald-300 sticky top-0 flex items-center">
              Top Contreebutors
              <span className="ml-2 bg-emerald-600/80 text-white text-xs font-bold px-3 py-1 rounded-full backdrop-blur-sm">
                LIVE RANKINGS
              </span>
            </h2>
            
            {/* CTA section */}
            <div className="mt-3 mb-3 p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
              <div className="flex flex-col">
                <div className="flex items-center mb-3">
                  <div className="text-5xl mr-3">🏆</div>
                  <h3 className="text-xl font-bold text-emerald-300">Join the Treederboard</h3>
                </div>
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <p className="text-white text-lg leading-relaxed">
                    Fund research to see your name on the Treederboard!
                  </p>
                  <div className="flex flex-wrap gap-4">
                    <Link 
                      href="/search"
                      className="inline-flex px-6 py-3 bg-emerald-600/80 hover:bg-emerald-600 backdrop-blur-md rounded-xl text-white font-semibold transition-colors"
                    >
                      Fund Research
                    </Link>
                    
                    <a 
                      href="https://twitter.com/intent/tweet?text=I'm%20helping%20to%20build%20the%20tree%20knowledge%20commons%20on%20Treekipedia!%20Check%20it%20out%20at%20https://treekipedia.silvi.earth"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex px-6 py-3 bg-zinc-800/40 hover:bg-zinc-800/60 backdrop-blur-md rounded-xl text-white font-semibold transition-colors items-center"
                    >
                      Share on <span className="ml-1 font-bold">𝕏</span>
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Loading state */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center p-12 text-white">
              <Loader2 className="h-12 w-12 animate-spin mb-4 text-emerald-300" />
              <p className="text-lg">Loading Treederboard data...</p>
            </div>
          )}

          {/* Error state */}
          {error && !isLoading && (
            <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-red-500/30 text-center">
              <AlertCircle className="h-10 w-10 text-red-400 mx-auto mb-4" />
              <p className="text-white text-lg leading-relaxed">{error}</p>
              <button 
                onClick={() => window.location.reload()}
                className="mt-4 inline-flex px-6 py-3 bg-emerald-600/80 hover:bg-emerald-600 backdrop-blur-md rounded-xl text-white font-semibold transition-colors"
              >
                Try Again
              </button>
            </div>
          )}

          {/* Data table */}
          {!isLoading && !error && (
            <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 overflow-auto max-h-[432px]">
              <table className="min-w-full divide-y divide-white/10">
                <thead className="bg-white/5">
                  <tr>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-emerald-300 uppercase tracking-wider w-16">
                      Rank
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-emerald-300 uppercase tracking-wider">
                      User
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-emerald-300 uppercase tracking-wider">
                      Wallet
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-emerald-300 uppercase tracking-wider w-28">
                      Points
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-emerald-300 uppercase tracking-wider w-28">
                      Trees
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {leaderboard.map((user, index) => (
                    <tr 
                      key={user.id} 
                      className={`hover:bg-white/10 transition-colors ${
                        index === 0 ? "border-l-4 border-yellow-500" : 
                        index === 1 ? "border-l-4 border-gray-400" : 
                        index === 2 ? "border-l-4 border-amber-700" : ""
                      }`}
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className={`text-base font-bold ${
                          index === 0 ? "text-yellow-500" : 
                          index === 1 ? "text-gray-400" : 
                          index === 2 ? "text-amber-700" : "text-gray-400"
                        }`}>
                          {index + 1}
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="text-base font-medium text-white">
                          {user.display_name || `Tree Steward #${user.id}`}
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="inline-flex items-center px-3 py-1 rounded-md bg-black/40 backdrop-blur-sm text-sm font-medium text-white/80">
                          <Link href={`/profile?address=${user.wallet_address}`}>
                            {formatAddress(user.wallet_address)}
                          </Link>
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="text-base font-bold text-emerald-300">{user.total_points}</div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="text-base text-white">{user.contribution_count}</div>
                      </td>
                    </tr>
                  ))}

                  {leaderboard.length === 0 && !isLoading && (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-white/80 text-lg">
                        No contributions yet. Be the first to fund research and join the Treederboard!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}