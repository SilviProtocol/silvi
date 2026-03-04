"use client"

import { useState, useRef, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useSession, signOut } from "next-auth/react"
import { Menu, X, User, LogOut, ChevronDown } from "lucide-react"
import { CreditBalance } from "./CreditBalance"
import { cn } from "@/lib/utils"

export function Navbar() {
  const pathname = usePathname()
  const { data: session, status } = useSession()

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  // Close user menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const routes = [
    {
      href: "/search",
      label: "Search",
      active: pathname === "/search" || pathname === "/",
    },
    {
      href: "/analysis",
      label: "Analysis",
      active: pathname === "/analysis",
    },
    {
      href: "/about",
      label: "About",
      active: pathname === "/about",
    },
  ]

  const toggleMobileMenu = () => {
    setMobileMenuOpen(!mobileMenuOpen)
  }

  const isAuthenticated = status === "authenticated" && session?.user

  // Get display info from session
  const userEmail = session?.user?.email
  const userName = session?.user?.name
  const userInitial = (userName?.[0] || userEmail?.[0] || "U").toUpperCase()

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-black/30 backdrop-blur-md border-b border-silvi-mint/20 shadow-md">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Link href="/" className="flex items-center z-10">
              <img
                src="/treekipedialogo.svg"
                alt="Treekipedia"
                className="h-8 text-silvi-mint filter brightness-100 saturate-0"
                style={{ filter: 'brightness(0) saturate(100%) invert(98%) sepia(5%) saturate(401%) hue-rotate(53deg) brightness(103%) contrast(94%)' }}
              />
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:flex ml-6 space-x-6">
              {routes.map((route) => (
                <Link
                  key={route.href}
                  href={route.href}
                  className={cn(
                    "text-white hover:text-emerald-300 font-medium transition-colors",
                    route.active && "text-emerald-300"
                  )}
                >
                  {route.label}
                </Link>
              ))}
            </div>
          </div>

          {/* Right side: Auth + Credits */}
          <div className="flex items-center space-x-3">
            {/* Credit Balance */}
            <div className="hidden md:block">
              <CreditBalance />
            </div>

            {/* Auth UI */}
            {status === "loading" ? (
              <div className="h-8 w-8 rounded-full bg-white/10 animate-pulse" />
            ) : isAuthenticated ? (
              <div ref={userMenuRef} className="relative">
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
                >
                  <div className="h-7 w-7 rounded-full bg-emerald-600 flex items-center justify-center text-white text-sm font-medium">
                    {userInitial}
                  </div>
                  <ChevronDown className={cn(
                    "h-3.5 w-3.5 text-white/60 transition-transform hidden sm:block",
                    userMenuOpen && "rotate-180"
                  )} />
                </button>

                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-lg bg-black/80 backdrop-blur-lg border border-white/10 shadow-xl py-1 z-50">
                    <div className="px-4 py-2 border-b border-white/10">
                      <p className="text-sm text-white font-medium truncate">
                        {userName || userEmail || "User"}
                      </p>
                      {userEmail && (
                        <p className="text-xs text-white/50 truncate">{userEmail}</p>
                      )}
                    </div>
                    <button
                      onClick={() => {
                        setUserMenuOpen(false)
                        signOut({ callbackUrl: "/" })
                      }}
                      className="w-full flex items-center space-x-2 px-4 py-2 text-sm text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                    >
                      <LogOut className="h-4 w-4" />
                      <span>Sign out</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Link
                href="/login"
                className="flex items-center space-x-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium transition-colors"
              >
                <User className="h-4 w-4" />
                <span>Sign In</span>
              </Link>
            )}

            {/* Mobile menu button */}
            <button
              className="md:hidden z-10 p-2 rounded-md text-white hover:bg-white/10"
              onClick={toggleMobileMenu}
            >
              {mobileMenuOpen ? (
                <X className="h-6 w-6" />
              ) : (
                <Menu className="h-6 w-6" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      <div
        className={`md:hidden fixed inset-0 bg-black/40 backdrop-blur-lg pt-16 px-6 transition-opacity duration-300 ${
          mobileMenuOpen
            ? 'opacity-100 z-40 pointer-events-auto'
            : 'opacity-0 -z-10 pointer-events-none'
        }`}
      >
        <div className="flex flex-col space-y-4 mt-4">
          {routes.map((route) => (
            <Link
              key={route.href}
              href={route.href}
              className={cn(
                "text-white py-3 px-4 rounded-lg hover:bg-white/10 font-medium text-lg flex items-center",
                route.active && "bg-white/5 border-l-2 border-emerald-300 pl-3 text-emerald-300"
              )}
              onClick={() => setMobileMenuOpen(false)}
            >
              {route.label}
            </Link>
          ))}

          <div className="pt-4 border-t border-white/20 space-y-3">
            {isAuthenticated ? (
              <button
                onClick={() => {
                  setMobileMenuOpen(false)
                  signOut({ callbackUrl: "/" })
                }}
                className="w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-lg text-white/70 hover:text-white hover:bg-white/10"
              >
                <LogOut className="h-5 w-5" />
                <span>Sign out ({userEmail || "User"})</span>
              </button>
            ) : (
              <Link
                href="/login"
                onClick={() => setMobileMenuOpen(false)}
                className="w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-medium"
              >
                <User className="h-5 w-5" />
                <span>Sign In</span>
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}
