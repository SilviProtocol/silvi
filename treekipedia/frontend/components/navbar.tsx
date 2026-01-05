"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Menu, X } from "lucide-react"
import { WalletConnectButton } from "./wallet-connect-button"
import { cn } from "@/lib/utils"

/**
 * Enhanced Navbar component combining elements from the current implementation
 * and the v0 design system for better mobile handling and UX
 */
export function Navbar() {
  const pathname = usePathname()

  // State management
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  
  // Routes for navigation
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

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-black/30 backdrop-blur-md border-b border-silvi-mint/20 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            {/* Image Logo */}
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

          {/* Right side: Wallet */}
          <div className="flex items-center space-x-4">
            {/* Wallet Connection */}
            <div className="wallet-container relative">
              <WalletConnectButton />
            </div>

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
      
      {/* Mobile menu - improved with better animations and structure */}
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

          <div className="pt-4 border-t border-white/20">
            <div className="flex justify-center" onClick={() => setMobileMenuOpen(false)}>
              <WalletConnectButton />
            </div>
          </div>
        </div>
      </div>
    </nav>
  )
}