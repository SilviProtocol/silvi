"use client";

import { useEffect } from "react";
import { Navbar } from "@/components/navbar";
import { useTour } from "@/context/tour-context";

export default function AboutPage() {
  const { autoStartTour } = useTour();

  useEffect(() => {
    autoStartTour('about');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="w-full min-h-screen">
        <div
          className="min-h-screen py-16 px-4 sm:px-6"
        >
          <div className="max-w-4xl mx-auto">
            <h1 data-tour="about-header" className="text-4xl font-bold tracking-tighter mb-8 text-white text-center">
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-emerald-300 via-green-200 to-teal-300 animate-gradient-x">
                The Tree Intelligence Commons
              </span>
            </h1>

            <div className="grid gap-6">
              {/* Overview Section */}
              <div data-tour="about-overview" className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                <div className="flex flex-col">
                  <div className="flex items-center mb-3">
                    <div className="text-5xl mr-3">🌐</div>
                    <h3 className="text-xl font-bold text-emerald-300">Overview</h3>
                  </div>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    Treekipedia is an open-source, comprehensive database of tree knowledge. Developed by Silvi, 
                    Treekipedia provides a unified, structured, and AI-enhanced repository of species data, 
                    reforestation methodologies, and ecological insights.
                  </p>
                  <p className="text-white text-lg leading-relaxed">
                    By integrating consolidated biodiversity data, AI research agents, and community-driven 
                    contributions, Treekipedia ensures reliable, transparent, and accessible tree knowledge 
                    for tree stewards, researchers, and citizen scientists worldwide.
                  </p>
                </div>
              </div>

              {/* Problem Section */}
              <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                <div className="flex flex-col">
                  <div className="flex items-center mb-3">
                    <div className="text-5xl mr-3">🔍</div>
                    <h3 className="text-xl font-bold text-emerald-300">The Problem: Fragmented Tree Knowledge</h3>
                  </div>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    Scientific and ecological data on trees are scattered across institutional archives, peer-reviewed 
                    studies, and community-driven sources, with over 70% of this data existing in unstructured, 
                    non-machine-readable formats.
                  </p>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    Local stewards and reforestation practitioners hold valuable field knowledge, yet this insight is 
                    often missing from centralized databases. These inefficiencies slow down reforestation efforts, 
                    ecological modeling, and sustainable land management.
                  </p>
                  <p className="text-white text-lg leading-relaxed">
                    As climate change reshapes ecosystems, tree habitat suitability and stewardship practices must evolve. 
                    There is an urgent need for a living, shared database that can adapt to real-world ecological changes.
                  </p>
                </div>
              </div>

              {/* Approach Section */}
              <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                <div className="flex flex-col">
                  <div className="flex items-center mb-3">
                    <div className="text-5xl mr-3">💡</div>
                    <h3 className="text-xl font-bold text-emerald-300">Our Approach: A Unified Database</h3>
                  </div>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    Treekipedia is designed as an interoperable knowledge hub, enabling institutions, researchers, 
                    and tree stewards to contribute, query, and verify tree-related information. It ensures transparency 
                    and accuracy by integrating AI-driven analytics, blockchain-verified data provenance, and 
                    decentralized validation models.
                  </p>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    At its core, Treekipedia consolidates species data, ecological insights, and reforestation methodologies 
                    into a structured, AI-enhanced repository. AI research agents autonomously extract, synthesize, and 
                    organize tree data from academic papers, government records, and community-contributed observations.
                  </p>
                  <p className="text-white text-lg leading-relaxed">
                    Beyond AI and blockchain verification, Treekipedia is community-driven. Tree stewards, researchers, 
                    and citizen scientists can contribute firsthand insights, validate data, and refine reforestation 
                    methodologies following standardized tree knowledge schemas.
                  </p>
                </div>
              </div>

              {/* How It Works Section */}
              <div data-tour="about-how-it-works" className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                <div className="flex flex-col">
                  <div className="flex items-center mb-3">
                    <div className="text-5xl mr-3">⚙️</div>
                    <h3 className="text-xl font-bold text-emerald-300">How It Works</h3>
                  </div>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    Treekipedia combines AI technology, blockchain verification, and community contributions 
                    to build a comprehensive tree intelligence system:
                  </p>
                  <div className="grid gap-4">
                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">1. Search for a Tree Species</h3>
                      <p className="text-base text-white/80">
                        Access our database of 50,000+ tree species with structured data on taxonomy, ecology, and habitat.
                      </p>
                    </div>
                    
                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">2. Discover Missing Information</h3>
                      <p className="text-base text-white/80">
                        Identify knowledge gaps in species data that represent opportunities for contribution.
                      </p>
                    </div>
                    
                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">3. Request Research</h3>
                      <p className="text-base text-white/80">
                        Click the Research button on any unresearched species to add it to the research queue for AI-powered data enrichment.
                      </p>
                    </div>

                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">4. Deep Research Process</h3>
                      <p className="text-base text-white/80">
                        Our AI conducts comprehensive research across global databases (IUCN, GBIF, POWO) and grey literature in multiple languages.
                      </p>
                    </div>
                    
                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">5. Earn Tree Points</h3>
                      <p className="text-base text-white/80">
                        Each contribution earns points displayed on the Treederboard, recognizing your impact in expanding tree knowledge.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Technical Infrastructure Section */}
              <div data-tour="about-tech" className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                <div className="flex flex-col">
                  <div className="flex items-center mb-3">
                    <div className="text-5xl mr-3">⛓️</div>
                    <h3 className="text-xl font-bold text-emerald-300">Technical Infrastructure</h3>
                  </div>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    Treekipedia leverages modern AI and database infrastructure:
                  </p>
                  <ul className="list-disc list-inside space-y-3 text-white/80 text-base pl-2">
                    <li>
                      <strong className="text-emerald-300">AI-Powered Research:</strong> Deep research using Claude AI across global botanical databases
                    </li>
                    <li>
                      <strong className="text-emerald-300">Multilingual Sources:</strong> Research spans English, Spanish, Portuguese, French, German and more
                    </li>
                    <li>
                      <strong className="text-emerald-300">Grey Literature Mining:</strong> Dissertations, FAO reports, and government forestry documents
                    </li>
                    <li>
                      <strong className="text-emerald-300">PostgreSQL + PostGIS:</strong> Geospatial database with 5.7M occurrence tiles
                    </li>
                    <li>
                      <strong className="text-emerald-300">FAIR-Compliant Insights:</strong> Structured provenance tracking for all research data
                    </li>
                  </ul>
                </div>
              </div>

              {/* Data Foundation Section */}
              <div data-tour="about-data" className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                <div className="flex flex-col">
                  <div className="flex items-center mb-3">
                    <div className="text-5xl mr-3">📊</div>
                    <h3 className="text-xl font-bold text-emerald-300">Data Foundation</h3>
                  </div>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    Treekipedia&apos;s foundation was built through extensive data collection, cleaning, and structuring:
                  </p>
                  <ul className="list-disc list-inside space-y-3 text-white/80 text-base pl-2">
                    <li>
                      <strong className="text-emerald-300">25M+ Raw Species Records:</strong> Aggregated from 10+ global biodiversity datasets
                    </li>
                    <li>
                      <strong className="text-emerald-300">50,000+ Unique Tree Species:</strong> After deduplication, taxonomy validation, and synonym resolution
                    </li>
                    <li>
                      <strong className="text-emerald-300">17.6M Observational Records:</strong> Capturing distribution and ecological data
                    </li>
                    <li>
                      <strong className="text-emerald-300">50+ Taxonomic & Ecological Attributes:</strong> Providing a standardized framework for knowledge retrieval
                    </li>
                    <li>
                      <strong className="text-emerald-300">Custom TaxonID System:</strong> Ensuring unique species identification and data consistency
                    </li>
                  </ul>
                </div>
              </div>

              {/* Roadmap Section */}
              <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                <div className="flex flex-col">
                  <div className="flex items-center mb-3">
                    <div className="text-5xl mr-3">🗺️</div>
                    <h3 className="text-xl font-bold text-emerald-300">2025 Roadmap</h3>
                  </div>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    Treekipedia is being developed through a structured roadmap to expand capabilities and increase community participation:
                  </p>
                  <div className="grid gap-4">
                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">Phase 1: v1.0 Launch (Earth Day)</h3>
                      <p className="text-base text-white/80">
                        Tree species database, AI-powered deep research, queue-based research workflow, insights provenance tracking.
                      </p>
                    </div>
                    
                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">Phase 2: Infrastructure</h3>
                      <p className="text-base text-white/80">
                        Blazegraph API deployment, data versioning, AI validation protocols.
                      </p>
                    </div>
                    
                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">Phase 3: Community</h3>
                      <p className="text-base text-white/80">
                        Working groups with scientists and conservationists, peer review system, governance mechanisms.
                      </p>
                    </div>
                    
                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">Phase 4: AI Scaling</h3>
                      <p className="text-base text-white/80">
                        Autonomous knowledge updates, credibility scoring systems, ecological modeling capabilities.
                      </p>
                    </div>
                    
                    <div className="p-4 rounded-lg bg-black/30 border border-white/10">
                      <h3 className="text-lg font-bold text-white mb-2">Phase 5: Global Rollout</h3>
                      <p className="text-base text-white/80">
                        Public API launch, institutional partnerships, and integration with monitoring and verification systems.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Silvi Connection */}
              <div className="p-5 rounded-xl bg-black/30 backdrop-blur-md border border-white/20 text-white">
                <div className="flex flex-col">
                  <div className="flex items-center mb-3">
                    <div className="text-5xl mr-3">🌱</div>
                    <h3 className="text-xl font-bold text-emerald-300">Silvi and Treekipedia</h3>
                  </div>
                  <p className="text-white text-lg leading-relaxed mb-4">
                    Treekipedia is developed and supported by <a href="https://www.silvi.earth/" target="_blank" rel="noopener noreferrer" className="text-emerald-300 font-bold hover:underline">Silvi</a>, a blockchain-powered 
                    reforestation protocol. Silvi has already integrated Treekipedia as its species data source within 
                    the Silvi App, making it the authoritative knowledge base for tree intelligence in Silvi&apos;s ecosystem.
                  </p>
                  <p className="text-white text-lg leading-relaxed">
                    This foundation sets the stage for Treekipedia&apos;s next evolution: an AI-enhanced, 
                    decentralized ecosystem for global tree intelligence.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}