"use client";

import { Navbar } from "@/components/navbar";
import { useAccount } from "wagmi";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";
import { getUserProfile, updateUserProfile } from "@/lib/api";
import Link from "next/link";
import { Check } from "lucide-react";

export default function ProfilePage() {
  const { address, isConnected } = useAccount();
  const [userProfile, setUserProfile] = useState<any>(null);
  const [displayName, setDisplayName] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    async function fetchUserProfile() {
      if (!address) {
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        const profile = await getUserProfile(address);
        setUserProfile(profile);
        setDisplayName(profile.display_name || "");
      } catch (error) {
        console.error("Failed to fetch user profile:", error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchUserProfile();
  }, [address]);

  const handleUpdateProfile = async () => {
    if (!address) return;

    try {
      setIsUpdating(true);
      setSaveSuccess(false); // Reset save success state
      
      const updatedProfile = await updateUserProfile(address, displayName);
      
      // Update the user profile with the new display name
      setUserProfile({
        ...userProfile,
        display_name: updatedProfile.display_name,
      });
      
      // Show success message
      setSaveSuccess(true);
      
      // Hide success message after 3 seconds
      setTimeout(() => {
        setSaveSuccess(false);
      }, 3000);
    } catch (error) {
      console.error("Failed to update profile:", error);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="w-full min-h-screen">
        <div
          className="min-h-screen py-12 px-4 sm:px-6"
        >
          <div className="max-w-4xl mx-auto">
            <h1 className="text-4xl font-bold tracking-tighter text-white mb-8">
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-emerald-300 via-green-200 to-teal-300 animate-gradient-x">
                My Profile
              </span>
            </h1>

            {!isConnected ? (
              <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-center text-white">
                <div className="flex flex-col items-center">
                  <div className="text-5xl mb-4">🔐</div>
                  <h3 className="text-xl font-bold text-emerald-300 mb-3">Wallet Not Connected</h3>
                  <p className="text-lg leading-relaxed">Connect your wallet to view your profile and sponsored trees</p>
                </div>
              </div>
            ) : isLoading ? (
              <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-center text-white">
                <div className="flex flex-col items-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-300 mx-auto mb-4"></div>
                  <p className="text-lg leading-relaxed">Loading your profile...</p>
                </div>
              </div>
            ) : (
              <div className="grid gap-6">
                {/* Profile Card */}
                <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                  <div className="flex flex-col">
                    <div className="flex items-center mb-3">
                      <div className="text-5xl mr-3">👤</div>
                      <h3 className="text-xl font-bold text-emerald-300">Profile Information</h3>
                    </div>

                    <div className="grid gap-4">
                      <div>
                        <label className="block text-base font-medium mb-1 text-white/80">Wallet Address</label>
                        <div className="p-3 rounded-lg bg-black/30 border border-white/10 font-mono text-base overflow-auto text-white">
                          {address}
                        </div>
                      </div>

                      <div>
                        <label htmlFor="displayName" className="block text-base font-medium mb-1 text-white/80">
                          Display Name
                        </label>
                        <div className="flex flex-col gap-2">
                          <div className="flex gap-2">
                            <input
                              id="displayName"
                              type="text"
                              value={displayName}
                              onChange={(e) => setDisplayName(e.target.value)}
                              placeholder="Enter display name"
                              className="p-3 rounded-lg bg-black/30 border border-white/10 w-full text-white"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  handleUpdateProfile();
                                }
                              }}
                            />
                            <Button 
                              onClick={handleUpdateProfile} 
                              disabled={isUpdating}
                              className="inline-flex px-6 py-3 bg-emerald-600/80 hover:bg-emerald-600 backdrop-blur-md rounded-xl text-white font-semibold transition-colors"
                            >
                              {isUpdating ? "Saving..." : "Save"}
                            </Button>
                          </div>
                          
                          {/* Success message */}
                          {saveSuccess && (
                            <div className="text-emerald-400 text-base px-2 py-1 rounded animate-pulse">
                              ✅ Display name saved successfully!
                            </div>
                          )}
                        </div>
                      </div>

                      <div>
                        <label className="block text-base font-medium mb-1 text-white/80">Tree Points</label>
                        <div className="p-3 rounded-lg bg-black/30 border border-white/10 text-white text-lg font-bold">
                          {userProfile?.total_points || 0} points
                        </div>
                      </div>

                      <div>
                        <label className="block text-base font-medium mb-1 text-white/80">Trees Researched</label>
                        <div className="p-3 rounded-lg bg-black/30 border border-white/10 text-white text-lg font-bold">
                          {userProfile?.contribution_count || 0} trees
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Combined Sponsorships and NFTs Card */}
                <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                  <div className="flex flex-col">
                    <div className="flex items-center mb-3">
                      <div className="text-5xl mr-3">🌳</div>
                      <h3 className="text-xl font-bold text-emerald-300">My Sponsored Trees</h3>
                    </div>
                    
                    {userProfile?.nfts && userProfile.nfts.length > 0 ? (
                      <div className="grid grid-cols-1 gap-4">
                        {userProfile.nfts.map((nft: any) => (
                          <div
                            key={nft.id}
                            className="p-4 rounded-lg bg-black/30 border border-white/10"
                          >
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center">
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-green-300/30 to-emerald-600/30 flex items-center justify-center mr-3">
                                  <span className="text-emerald-300 font-bold">#{nft.global_id}</span>
                                </div>
                                <div>
                                  <Link 
                                    href={`/species/${nft.taxon_id}`}
                                    className="text-lg font-bold text-emerald-300 hover:underline"
                                  >
                                    {/* Use scientific name when available, otherwise fall back to taxon_id */}
                                    <span className="italic">{nft.metadata?.species || nft.taxon_id}</span>
                                  </Link>
                                  <div className="text-base text-white/80">
                                    Research Contreebution #{nft.global_id}
                                  </div>
                                </div>
                              </div>
                              <div className="text-sm text-white/70">
                                {new Date(nft.created_at).toLocaleDateString()}
                              </div>
                            </div>
                            <div className="flex justify-between text-sm text-white/80">
                              <div className="flex items-center gap-3">
                                <div className="flex items-center">
                                  <Check className="w-4 h-4 text-green-500 mr-1" />
                                  <span>Research Complete</span>
                                </div>
                                {nft.metadata?.chain && (
                                  <div className="px-2 py-0.5 bg-black/40 rounded-full text-xs font-medium">
                                    {nft.metadata.chain.charAt(0).toUpperCase() + nft.metadata.chain.slice(1)}
                                  </div>
                                )}
                              </div>
                              <Link
                                href={`/species/${nft.taxon_id}`}
                                className="text-emerald-400 hover:text-emerald-300"
                              >
                                View Species →
                              </Link>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center p-8">
                        <p className="text-lg leading-relaxed mb-2">You haven't sponsored any trees yet</p>
                        <p className="text-base text-white/80 mb-4">
                          Fund research for a tree species to earn your first Contreebution NFT
                        </p>
                        <Link 
                          href="/search"
                          className="inline-flex px-6 py-3 bg-emerald-600/80 hover:bg-emerald-600 backdrop-blur-md rounded-xl text-white font-semibold transition-colors"
                        >
                          Sponsor a Tree
                        </Link>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}