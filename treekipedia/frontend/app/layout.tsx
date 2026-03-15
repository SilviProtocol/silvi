import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import { Suspense } from "react";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";

export const metadata: Metadata = {
  title: {
    default: 'Treekipedia',
    template: '%s | Treekipedia'
  },
  description: 'Treekipedia is an open-source, comprehensive database of tree knowledge.',
  keywords: ['Trees', 'Ecology', 'Reforestation', 'Environment', 'Climate Change', 'Botany', 'Species Database', 'Conservation'],
};

// Viewport must be in a separate export as per Next.js 14+ recommendations
export const viewport = {
  width: 'device-width',
  initialScale: 1
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" style={{ colorScheme: "dark" }}>
      <body className="font-sans antialiased min-h-screen bg-[url('/background7.png')] bg-fixed bg-cover bg-center text-white flex flex-col">
        <Providers>
          <Navbar />
          <main className="flex-1 pt-16">
            <Suspense>
              {children}
            </Suspense>
          </main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
