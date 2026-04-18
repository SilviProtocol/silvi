"use client"

import { useEffect, useState } from "react"
import { useSession, signOut } from "next-auth/react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Coins, Loader2, LogOut, Pencil, Check, X, ArrowRight, Mail, Calendar } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useProfile } from "@/hooks/useProfile"
import toast from "react-hot-toast"

export default function ProfilePage() {
  const router = useRouter()
  const { status } = useSession()
  const { profile, credits, isLoading, error, update } = useProfile()

  const [editing, setEditing] = useState(false)
  const [nameDraft, setNameDraft] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (status === "unauthenticated") router.push("/login")
  }, [status, router])

  useEffect(() => {
    if (profile?.display_name) setNameDraft(profile.display_name)
  }, [profile?.display_name])

  const startEdit = () => {
    setNameDraft(profile?.display_name || "")
    setEditing(true)
  }

  const cancelEdit = () => {
    setNameDraft(profile?.display_name || "")
    setEditing(false)
  }

  const saveName = async () => {
    const trimmed = nameDraft.trim()
    if (!trimmed || trimmed === profile?.display_name) {
      setEditing(false)
      return
    }
    setSaving(true)
    try {
      await update({ display_name: trimmed })
      toast.success("Display name updated")
      setEditing(false)
    } catch {
      toast.error("Failed to update display name")
    } finally {
      setSaving(false)
    }
  }

  if (status === "loading" || (isLoading && !profile)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-white/50" />
      </div>
    )
  }

  if (status !== "authenticated") return null

  const displayName = profile?.display_name || profile?.email || "Your Account"
  const avatarUrl = profile?.avatar_url
  const initial = (displayName[0] || "U").toUpperCase()

  const joinedDate = profile?.created_at
    ? new Date(profile.created_at).toLocaleDateString("en-US", { month: "long", year: "numeric" })
    : null

  return (
    <div className="min-h-screen py-8">
      <div className="max-w-3xl mx-auto px-4 space-y-6">
        <h1 className="text-2xl font-semibold text-white px-1">Your Profile</h1>

        {error && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {/* Identity Card */}
        <div className="rounded-2xl bg-black/40 backdrop-blur-md border border-white/15 p-6">
          <div className="flex items-start gap-5">
            {/* Avatar */}
            {avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatarUrl}
                alt={displayName}
                className="h-20 w-20 rounded-full border-2 border-white/10 object-cover shrink-0"
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="h-20 w-20 rounded-full bg-emerald-600 border-2 border-white/10 flex items-center justify-center text-white text-2xl font-semibold shrink-0">
                {initial}
              </div>
            )}

            {/* Identity */}
            <div className="flex-1 min-w-0">
              {/* Display name (editable) */}
              {editing ? (
                <div className="flex items-center gap-2 mb-2">
                  <Input
                    value={nameDraft}
                    onChange={(e) => setNameDraft(e.target.value)}
                    placeholder="Display name"
                    autoFocus
                    disabled={saving}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveName()
                      if (e.key === "Escape") cancelEdit()
                    }}
                    className="bg-white/5 border-white/20 text-white placeholder:text-white/40 focus-visible:ring-emerald-400 text-lg"
                  />
                  <Button
                    size="sm"
                    onClick={saveName}
                    disabled={saving}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={cancelEdit}
                    disabled={saving}
                    className="text-white/60 hover:text-white hover:bg-white/5"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2 mb-2 group">
                  <h2 className="text-xl font-semibold text-white truncate">{displayName}</h2>
                  <button
                    onClick={startEdit}
                    className="opacity-0 group-hover:opacity-100 text-white/50 hover:text-white transition-opacity"
                    aria-label="Edit display name"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                </div>
              )}

              {/* Email */}
              {profile?.email && (
                <div className="flex items-center gap-2 text-sm text-white/60 mb-1">
                  <Mail className="h-3.5 w-3.5" />
                  <span className="truncate">{profile.email}</span>
                </div>
              )}

              {/* Joined date */}
              {joinedDate && (
                <div className="flex items-center gap-2 text-sm text-white/50">
                  <Calendar className="h-3.5 w-3.5" />
                  <span>Joined {joinedDate}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Credits Summary */}
        <div className="rounded-2xl bg-black/40 backdrop-blur-md border border-white/15 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-white">Credits</h2>
            <Link href="/credits">
              <Button variant="ghost" className="text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10">
                Manage credits
                <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </Link>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <div className="text-sm text-white/50 mb-1">Balance</div>
              <div className="text-2xl font-semibold text-white flex items-center gap-2">
                <Coins className="h-5 w-5 text-amber-400" />
                {credits ? credits.balance.toLocaleString() : "..."}
              </div>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <div className="text-sm text-white/50 mb-1">Total Earned</div>
              <div className="text-lg font-medium text-emerald-400">
                {credits ? credits.lifetime_purchased.toLocaleString() : "..."}
              </div>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <div className="text-sm text-white/50 mb-1">Total Spent</div>
              <div className="text-lg font-medium text-white/70">
                {credits ? credits.lifetime_spent.toLocaleString() : "..."}
              </div>
            </div>
          </div>
        </div>

        {/* Account Actions */}
        <div className="rounded-2xl bg-black/40 backdrop-blur-md border border-white/15 p-6">
          <h2 className="text-lg font-medium text-white mb-4">Account</h2>
          <Button
            variant="ghost"
            onClick={() => signOut({ callbackUrl: "/" })}
            className="w-full justify-start text-white/70 hover:text-white hover:bg-white/5"
          >
            <LogOut className="h-4 w-4 mr-2" />
            Sign out
          </Button>
        </div>
      </div>
    </div>
  )
}
