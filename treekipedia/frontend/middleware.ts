import { auth } from "@/auth"
import { NextResponse } from "next/server"

const protectedPrefixes = ["/profile", "/saved"]

export default auth((req) => {
  const { pathname } = req.nextUrl
  const isProtected = protectedPrefixes.some((p) => pathname.startsWith(p))

  if (isProtected && !req.auth) {
    return NextResponse.redirect(
      new URL(`/login?callbackUrl=${encodeURIComponent(pathname)}`, req.url)
    )
  }

  return NextResponse.next()
})

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
}
