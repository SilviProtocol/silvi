"use client"

import { useState } from "react"
import { signIn } from "next-auth/react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Mail, ArrowLeft, Loader2 } from "lucide-react"
import toast from "react-hot-toast"

const DJANGO_API_URL = process.env.NEXT_PUBLIC_DJANGO_API_URL || "https://api.silvi.earth/"

type Step = "entry" | "verify-otp"

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const callbackUrl = searchParams.get("callbackUrl") || "/"

  const [step, setStep] = useState<Step>("entry")
  const [email, setEmail] = useState("")
  const [otp, setOtp] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSendOTP = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return

    setLoading(true)
    try {
      const res = await fetch(`${DJANGO_API_URL}auth/login/otp/send/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || data.error || "Failed to send verification code")
      }

      toast.success("Verification code sent to your email")
      setStep("verify-otp")
    } catch (error: any) {
      toast.error(error.message || "Failed to send verification code")
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!otp.trim()) return

    setLoading(true)
    try {
      const res = await fetch(`${DJANGO_API_URL}auth/login/otp/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), code: otp.trim() }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || data.error || "Invalid verification code")
      }

      const { access, refresh } = await res.json()

      const result = await signIn("token-login", {
        access,
        refresh,
        email: email.trim(),
        redirect: false,
        callbackUrl,
      })

      if (result?.error) {
        throw new Error("Sign in failed")
      }

      toast.success("Signed in successfully")
      router.push(callbackUrl)
    } catch (error: any) {
      toast.error(error.message || "Verification failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
      <Card className="w-full max-w-md bg-black/40 backdrop-blur-md border-white/10">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl text-white">
            {step === "entry" ? "Sign in to Treekipedia" : "Enter verification code"}
          </CardTitle>
          <CardDescription className="text-white/60">
            {step === "entry"
              ? "Access your research history, saved analyses, and more"
              : `We sent a code to ${email}`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === "entry" && (
            <>
              <form onSubmit={handleSendOTP} className="space-y-3">
                <Input
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="bg-white/5 border-white/20 text-white placeholder:text-white/40 focus-visible:ring-emerald-400"
                />
                <Button
                  type="submit"
                  disabled={loading || !email.trim()}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Mail className="h-4 w-4" />
                  )}
                  Continue with Email
                </Button>
              </form>

              <div className="relative py-1">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-white/10" />
                </div>
                <div className="relative flex justify-center">
                  <span className="bg-black/40 px-2 text-xs uppercase tracking-wider text-white/40">or</span>
                </div>
              </div>

              <Button
                type="button"
                onClick={() => signIn("google", { callbackUrl })}
                disabled={loading}
                className="w-full bg-white text-gray-900 hover:bg-gray-100"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
              </Button>
            </>
          )}

          {step === "verify-otp" && (
            <>
              <form onSubmit={handleVerifyOTP} className="space-y-3">
                <Input
                  type="text"
                  placeholder="Enter 6-digit code"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  required
                  maxLength={6}
                  autoFocus
                  className="bg-white/5 border-white/20 text-white text-center text-2xl tracking-widest placeholder:text-white/40 placeholder:text-base placeholder:tracking-normal focus-visible:ring-emerald-400"
                />
                <Button
                  type="submit"
                  disabled={loading || otp.length < 6}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "Verify & Sign In"
                  )}
                </Button>
              </form>

              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setStep("entry")
                  setOtp("")
                }}
                className="w-full text-white/60 hover:text-white hover:bg-white/5"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
