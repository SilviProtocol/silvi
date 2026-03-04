import { getSession } from "next-auth/react"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://treekipedia-api.silvi.earth"

/**
 * Fetch wrapper that adds the Django JWT from the NextAuth session
 * as a Bearer token to Treekipedia Express API calls.
 *
 * Use this for protected endpoints (e.g., /user/*).
 * Falls back to unauthenticated request if no session.
 */
export async function fetchWithAuth(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const session = await getSession()
  const token = (session?.user as any)?.access

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  }

  if (token) {
    ;(headers as Record<string, string>)["Authorization"] = `Bearer ${token}`
  }

  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`

  const response = await fetch(url, {
    ...options,
    headers,
  })

  // If we get a 401, the token may have expired mid-request.
  // The caller can handle this (e.g., redirect to login).
  return response
}

/**
 * Typed JSON fetch with auth — convenience wrapper
 */
export async function fetchJsonWithAuth<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetchWithAuth(path, options)

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }))
    throw new Error(error.error || error.message || `Request failed: ${response.status}`)
  }

  return response.json()
}
