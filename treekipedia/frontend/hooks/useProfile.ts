"use client"

import { useState, useEffect, useCallback } from "react"
import { useSession } from "next-auth/react"
import { getUserProfile, updateUserProfile, UserProfile } from "@/lib/user"
import type { CreditBalance } from "@/lib/credits"

export function useProfile() {
  const { status } = useSession()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [credits, setCredits] = useState<CreditBalance | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isAuthenticated = status === "authenticated"

  const refresh = useCallback(async () => {
    if (!isAuthenticated) {
      setProfile(null)
      setCredits(null)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await getUserProfile()
      setProfile(data.profile)
      setCredits(data.credits)
    } catch (err: any) {
      setError(err?.message || "Failed to load profile")
    } finally {
      setIsLoading(false)
    }
  }, [isAuthenticated])

  useEffect(() => {
    refresh()
  }, [refresh])

  const update = useCallback(
    async (updates: Partial<Pick<UserProfile, "email" | "display_name" | "avatar_url" | "preferences">>) => {
      const data = await updateUserProfile(updates)
      setProfile(data.profile)
      setCredits(data.credits)
      return data.profile
    },
    []
  )

  return { profile, credits, isLoading, error, refresh, update }
}
