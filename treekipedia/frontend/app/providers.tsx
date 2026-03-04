"use client"

import React, { useState } from 'react'
import { SessionProvider } from 'next-auth/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { ThemeProvider } from 'next-themes'
import { Toaster as SonnerToaster } from 'sonner'

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
    <SessionProvider>
      <ThemeProvider disableTransitionOnChange skipInitialClientCheck>
        <QueryClientProvider client={queryClient}>
          {children}
          <Toaster position="top-right" />
          <SonnerToaster position="top-right" />
        </QueryClientProvider>
      </ThemeProvider>
    </SessionProvider>
  )
}
