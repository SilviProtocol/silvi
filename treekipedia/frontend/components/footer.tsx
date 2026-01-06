import Link from "next/link"
import { Github, Twitter } from "lucide-react"

export function Footer() {
  return (
    <footer className="bg-black/30 backdrop-blur-md border-t border-white/10 text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Treekipedia</h3>
            <p className="text-sm text-white/70">
              The open encyclopedia of trees, powered by community research and AI.
            </p>
            <div className="flex items-center space-x-4">
              <a 
                href="https://twitter.com/silviprotocol" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-white/70 hover:text-white transition-colors"
              >
                <Twitter className="h-5 w-5" />
                <span className="sr-only">Twitter</span>
              </a>
              <a 
                href="https://github.com/SilviProtocol/silvi-open/tree/master" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-white/70 hover:text-white transition-colors"
              >
                <Github className="h-5 w-5" />
                <span className="sr-only">GitHub</span>
              </a>
            </div>
          </div>
          
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Quick Links</h3>
            <nav className="flex flex-col space-y-2">
              <Link
                href="/search"
                className="text-white/70 hover:text-white transition-colors text-sm"
              >
                Search
              </Link>
              <Link
                href="/analysis"
                className="text-white/70 hover:text-white transition-colors text-sm"
              >
                Analysis
              </Link>
              <Link
                href="/about"
                className="text-white/70 hover:text-white transition-colors text-sm"
              >
                About
              </Link>
            </nav>
          </div>
          
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Data Sources</h3>
            <p className="text-xs text-white/60 mb-2">
              Treekipedia aggregates data from 13+ major biodiversity databases:
            </p>
            <div className="grid grid-cols-2 gap-1 text-xs">
              <a 
                href="https://www.gbif.org/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                GBIF
              </a>
              <a 
                href="https://www.inaturalist.org/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                iNaturalist
              </a>
              <a 
                href="https://www.idigbio.org/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                iDigBio
              </a>
              <a 
                href="https://nbnatlas.org/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                NBN Atlas
              </a>
              <a 
                href="https://www.sibbr.gov.br/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                SiBBr
              </a>
              <a 
                href="https://specieslink.net/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                SpeciesLink
              </a>
              <a 
                href="https://data.nhm.ac.uk/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                NHM Portal
              </a>
              <a 
                href="https://biorepo.neonscience.org/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                NEON
              </a>
              <a 
                href="https://obis.org/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                OBIS
              </a>
              <a 
                href="https://jabot.jbrj.gov.br/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                Jabot
              </a>
              <a 
                href="https://floradobrasil.jbrj.gov.br/reflora/" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                Reflora
              </a>
              <a 
                href="https://research.fs.usda.gov/programs/fia" 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-white/70 hover:text-white transition-colors"
              >
                FIA-USDA
              </a>
            </div>
          </div>
        </div>
        
        <div className="mt-6 pt-4 border-t border-white/10">
          <div className="flex flex-col md:flex-row justify-between items-center text-sm text-white/50">
            <p>© {new Date().getFullYear()} Silvi Earth. All rights reserved.</p>
            <div className="flex space-x-4 mt-4 md:mt-0">
              <a 
                href="https://silvi.earth/terms" 
                target="_blank" 
                rel="noopener noreferrer"
                className="hover:text-white/80 transition-colors"
              >
                Terms of Service
              </a>
              <a 
                href="https://silvi.earth/privacy" 
                target="_blank" 
                rel="noopener noreferrer"
                className="hover:text-white/80 transition-colors"
              >
                Privacy Policy
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}