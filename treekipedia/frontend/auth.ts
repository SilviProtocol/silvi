import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"
import Google from "next-auth/providers/google"

const DJANGO_API_URL = process.env.NEXT_PUBLIC_DJANGO_API_URL || "https://api.silvi.earth/"

const refreshAccessToken = async (refreshToken: string) => {
  try {
    const response = await fetch(`${DJANGO_API_URL}auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken }),
    })

    if (!response.ok) {
      throw new Error(`Refresh failed: ${response.status}`)
    }

    const refreshedTokens = await response.json()

    return {
      access: refreshedTokens.access,
      refresh: refreshedTokens.refresh || refreshToken,
      expires: refreshedTokens.expires_in
        ? Math.floor(Date.now() / 1000) + refreshedTokens.expires_in
        : Math.floor(Date.now() / 1000) + (5 * 60),
    }
  } catch (error) {
    console.error('Token refresh error:', error)
    return null
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  secret: process.env.NEXTAUTH_SECRET,
  trustHost: true,
  providers: [
    // OTP login — backend already verified user and returned tokens
    Credentials({
      id: 'token-login',
      name: 'Token',
      credentials: {
        access: { label: 'Access Token', type: 'text' },
        refresh: { label: 'Refresh Token', type: 'text' },
      },
      async authorize(credentials) {
        if (credentials?.access && credentials?.refresh) {
          return {
            id: 'token-user',
            access: credentials.access as string,
            refresh: credentials.refresh as string,
          } as any
        }
        return null
      },
    }),
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    async signIn({ user, account, profile }) {
      // Google OAuth: exchange Google id_token for Django JWT
      if (account?.provider === "google") {
        try {
          const response = await fetch(`${DJANGO_API_URL}auth/google_login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              id_token: account.id_token,
              email: profile?.email,
              given_name: (profile as any)?.given_name,
              family_name: (profile as any)?.family_name,
            }),
          })

          if (!response.ok) return false

          const data = await response.json()
          ;(user as any).access = data.access
          ;(user as any).refresh = data.refresh
          return true
        } catch (error) {
          console.error('Google sign in error:', error)
          return false
        }
      }
      return true
    },
    async jwt({ token, user, account, trigger }: any) {
      if (trigger === "signOut") return {}

      // Initial sign in — store tokens + user info
      if (account && user) {
        return {
          ...token,
          access: (user as any).access,
          refresh: (user as any).refresh,
          expires: (user as any).accessExpires || Math.floor(Date.now() / 1000) + (5 * 60),
          name: user.name || token.name,
          email: user.email || token.email,
        }
      }

      if (!token.access) return {}

      // Refresh 1 minute before expiry
      const bufferTime = 1 * 60 * 1000
      if (token.expires && Date.now() < ((token.expires as number) * 1000 - bufferTime)) {
        return token
      }

      if (!token.refresh) return {}

      const refreshedTokens = await refreshAccessToken(token.refresh as string)
      if (refreshedTokens) {
        return {
          ...token,
          access: refreshedTokens.access,
          refresh: refreshedTokens.refresh,
          expires: refreshedTokens.expires,
        }
      }
      return {}
    },
    async session({ session, token }: any) {
      if (token && token.access) {
        return {
          ...session,
          user: {
            ...session.user,
            access: token.access,
            refresh: token.refresh,
            name: token.name || session.user?.name,
            email: token.email || session.user?.email,
          },
          error: token.error,
        }
      }
      return session
    },
  },
  events: {
    async signOut(message: any) {
      if (message.token?.refresh) {
        try {
          await fetch(`${DJANGO_API_URL}auth/token/revoke/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: message.token.refresh }),
          })
        } catch {}
      }
    },
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
  session: {
    maxAge: 24 * 60 * 60,
    strategy: 'jwt',
    updateAge: 2 * 60,
  },
  jwt: {
    maxAge: 24 * 60 * 60,
  },
})
