import { fetchJsonWithAuth } from "./auth-api"
import type { CreditBalance } from "./credits"

export interface UserProfile {
  id: number
  silvi_user_id: number
  email: string | null
  display_name: string | null
  avatar_url: string | null
  preferences: Record<string, any>
  created_at: string
  last_seen_at: string
}

export interface ProfileResponse {
  success: boolean
  profile: UserProfile | null
  credits: CreditBalance
  is_new?: boolean
}

export async function getUserProfile(): Promise<ProfileResponse> {
  return fetchJsonWithAuth<ProfileResponse>("/api/user/profile")
}

export async function updateUserProfile(
  updates: Partial<Pick<UserProfile, "email" | "display_name" | "avatar_url" | "preferences">>
): Promise<ProfileResponse> {
  return fetchJsonWithAuth<ProfileResponse>("/api/user/profile", {
    method: "POST",
    body: JSON.stringify(updates),
  })
}
