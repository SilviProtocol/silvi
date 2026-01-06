"use client"

import { useState, useEffect } from 'react'
import { useAccount } from 'wagmi'
import { getUserSponsorships } from '@/lib/api'
import { Loader2, Leaf, Check, AlertCircle, Clock } from 'lucide-react'
import Link from 'next/link'

export function SponsorshipStatus() {
  const { address } = useAccount()
  const [sponsorships, setSponsorships] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!address) return

    const fetchSponsorships = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const data = await getUserSponsorships(address)
        setSponsorships(data)
      } catch (err: any) {
        console.error('Error fetching sponsorships:', err)
        setError(err.message || 'Failed to load sponsorships')
      } finally {
        setIsLoading(false)
      }
    }

    fetchSponsorships()
  }, [address])

  // Function to get status icon
  const getStatusIcon = (status: string, researchStatus: string | undefined) => {
    if (status === 'pending') return <Clock className="w-4 h-4 text-yellow-500" />
    if (status === 'confirmed' && (!researchStatus || researchStatus === 'pending')) 
      return <Clock className="w-4 h-4 text-blue-500" />
    if (researchStatus === 'researching') 
      return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
    if (researchStatus === 'completed') 
      return <Check className="w-4 h-4 text-green-500" />
    if (researchStatus === 'failed') 
      return <AlertCircle className="w-4 h-4 text-red-500" />
    
    return <Leaf className="w-4 h-4 text-gray-500" />
  }

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return new Intl.DateTimeFormat('en-US', { 
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    }).format(date)
  }

  if (!address) {
    return (
      <div className="rounded-lg bg-black/30 backdrop-blur-md p-4 border border-white/10 text-center text-white/70">
        Connect your wallet to see your sponsorships
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="rounded-lg bg-black/30 backdrop-blur-md p-4 border border-white/10 flex items-center justify-center text-white">
        <Loader2 className="w-5 h-5 mr-2 animate-spin" />
        Loading sponsorships...
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg bg-black/30 backdrop-blur-md p-4 border border-red-500/30 text-red-400">
        <AlertCircle className="w-5 h-5 mr-2 inline-block" />
        {error}
      </div>
    )
  }

  if (sponsorships.length === 0) {
    return (
      <div className="rounded-lg bg-black/30 backdrop-blur-md p-4 border border-white/10 text-center text-white/70">
        You haven't sponsored any species yet
      </div>
    )
  }

  return (
    <div className="rounded-lg bg-black/30 backdrop-blur-md p-4 border border-white/10 text-white">
      <h3 className="font-semibold mb-4 flex items-center">
        <Leaf className="w-5 h-5 mr-2 text-emerald-400" />
        Your Sponsored Species
      </h3>
      
      <div className="space-y-3">
        {sponsorships.map((sponsorship) => (
          <div key={sponsorship.transaction_hash} className="border border-white/10 rounded-md p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm text-white/70">
                {formatDate(sponsorship.payment_timestamp)}
              </div>
              <div className="text-sm font-medium text-white">
                {sponsorship.total_amount} USDC
              </div>
            </div>
            
            <div className="space-y-2">
              {/* Map through taxon_ids array if multiple species */}
              {Array.isArray(sponsorship.taxon_ids) && sponsorship.taxon_ids.map((taxonId: string, index: number) => (
                <div key={taxonId} className="flex items-center justify-between">
                  <div className="flex items-center">
                    {getStatusIcon(
                      sponsorship.payment_status,
                      // We don't have individual research status in the summary view
                      sponsorship.completed_count > index ? 'completed' : 'pending'
                    )}
                    <Link 
                      href={`/species/${taxonId}`}
                      className="ml-2 text-emerald-400 hover:underline"
                    >
                      {taxonId}
                    </Link>
                  </div>
                  <div className="text-xs text-white/50">
                    {sponsorship.chain}
                  </div>
                </div>
              ))}
              
              {/* Show status indicator */}
              <div className="text-xs flex justify-between mt-1">
                <span className="text-white/70">
                  Status: 
                  <span className={`ml-1 ${
                    sponsorship.payment_status === 'completed' ? 'text-green-500' :
                    sponsorship.payment_status === 'confirmed' ? 'text-blue-500' :
                    'text-yellow-500'
                  }`}>
                    {sponsorship.payment_status.charAt(0).toUpperCase() + sponsorship.payment_status.slice(1)}
                  </span>
                </span>
                <span className="text-white/70">
                  {sponsorship.completed_count}/{sponsorship.species_count} completed
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}