"use client"

import React, { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createConfig, http, WagmiProvider, createStorage } from 'wagmi'
import { injected } from 'wagmi/connectors'
import { base, baseSepolia, celo, celoAlfajores, optimism, optimismSepolia, arbitrum, arbitrumSepolia } from 'wagmi/chains'
import { Toaster } from 'react-hot-toast'
import { ThemeProvider } from 'next-themes'
import { Toaster as SonnerToaster } from 'sonner'
import { TourProvider } from '@/context/tour-context'
import { TourButton } from '@/components/tour-button'

// Configure chains based on the spec (Base, Celo, Optimism, Arbitrum - mainnet and testnet)
const chains = [
  base,
  baseSepolia,
  celo,
  celoAlfajores,
  optimism,
  optimismSepolia,
  arbitrum,
  arbitrumSepolia
] as const

// Get Infura API key from environment
const infuraApiKey = process.env.NEXT_PUBLIC_INFURA_API_KEY || '03ccdfb9f1b1421b803e7c9e0fbee198';

// Create wagmi config with connectors and providers
const config = createConfig({
  chains,
  connectors: [
    injected()
  ],
  transports: {
    [base.id]: http(`https://base-mainnet.infura.io/v3/${infuraApiKey}`),
    [baseSepolia.id]: http(`https://base-sepolia.infura.io/v3/${infuraApiKey}`),
    [celo.id]: http(`https://celo-mainnet.infura.io/v3/${infuraApiKey}`),
    [celoAlfajores.id]: http(`https://celo-alfajores.infura.io/v3/${infuraApiKey}`),
    [optimism.id]: http(`https://optimism-mainnet.infura.io/v3/${infuraApiKey}`),
    [optimismSepolia.id]: http(`https://optimism-sepolia.infura.io/v3/${infuraApiKey}`),
    [arbitrum.id]: http(`https://arbitrum-mainnet.infura.io/v3/${infuraApiKey}`),
    [arbitrumSepolia.id]: http(`https://arbitrum-sepolia.infura.io/v3/${infuraApiKey}`),
  },
  storage: createStorage({ 
    storage: typeof window !== 'undefined' ? window.localStorage : undefined 
  }),
})

export default function Providers({ children }: { children: React.ReactNode }) {
  // Create React Query client
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // 1 minute
        refetchOnWindowFocus: false,
      },
    },
  }))

  return (
    // Use ThemeProvider without modifying HTML attributes to avoid hydration issues
    <ThemeProvider disableTransitionOnChange skipInitialClientCheck>
      <WagmiProvider config={config}>
        <QueryClientProvider client={queryClient}>
          <TourProvider>
            {children}
            <TourButton />
          </TourProvider>
          <Toaster position="top-right" />
          <SonnerToaster position="top-right" />
        </QueryClientProvider>
      </WagmiProvider>
    </ThemeProvider>
  )
}