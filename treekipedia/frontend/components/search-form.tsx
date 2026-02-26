"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Leaf, Loader2, Search } from "lucide-react";
import { useAccount } from 'wagmi';
import { toast } from "react-hot-toast";
import { getSpeciesSuggestions } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

// Define suggestion interface from API documentation 
// Based on /species/suggest endpoint in API.md and test results
interface Suggestion {
  taxon_id: string;
  common_name: string;
  species: string; // Legacy scientific name field
  species_scientific_name?: string; // New scientific name field
  accepted_scientific_name?: string; // Not used in our UI
}

interface SearchFormProps {
  placeholder?: string;
}

export function SearchForm({ placeholder = "Search 67,743 tree species & subspecies..." }: SearchFormProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") || "");
  const { isConnected } = useAccount();
  const [isFocused, setIsFocused] = useState(false);
  const [forceKeepOpen, setForceKeepOpen] = useState(false);

  // Simple, clean state management - just loading and suggestions
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  
  // Keep dropdown open whenever there is a query or when explicitly forced
  const keepDropdownOpen = (query && query.length >= 2) || forceKeepOpen;
  
  // Simple effect to fetch data when query changes - no dependencies on loading state
  useEffect(() => {
    // Skip API call if query is too short
    if (!query || query.length < 2) {
      setSuggestions([]);
      return;
    }
    
    // Log that we're fetching data with valid query
    console.log(`Starting to fetch data for "${query}" - length: ${query.length}`);
    
    // Track if the component is still mounted
    let isMounted = true;
    
    // Start loading
    setIsLoading(true);
    
    // Function to fetch data from the API with CORS support
    const fetchData = async () => {
      try {
        console.log(`Fetching suggestions for query: ${query}`);
        
        // Use environment variable, fallback to production for deployed builds
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth';
        const response = await fetch(
          `${API_URL}/species/suggest?query=${encodeURIComponent(query)}`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json'
            },
            // Don't use credentials for now to simplify debugging
            credentials: 'omit'
          }
        );
        
        // Only update state if component is still mounted
        if (!isMounted) return;
        
        if (!response.ok) {
          throw new Error(`API Error: ${response.status}`);
        }
        
        // Parse the JSON response
        const data = await response.json();
        console.log(`API returned ${data.length} results`);
        
        // Update the suggestions state
        setSuggestions(data);
      } catch (error) {
        console.error("Fetch error:", error);
        if (isMounted) {
          setSuggestions([]);
        }
      } finally {
        // Always end loading if component is mounted
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };
    
    // Add a small delay to avoid excessive calls while typing
    const timer = setTimeout(fetchData, 300);
    
    // Clean up function
    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [query]); // Only depend on query - removed isFocused dependency to prevent data loss

  // State to track which suggestion cards are expanded
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});
  
  // Toggle expand/collapse for a specific card
  const toggleCardExpansion = (index: string, event: React.MouseEvent) => {
    // Stop the click from propagating to parent (which would navigate to species)
    event.stopPropagation();
    event.preventDefault();
    
    // Ensure the dropdown stays open
    setForceKeepOpen(true);
    
    // Update expanded state for this card
    setExpandedCards(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };
  
  // Format common names by prioritizing the matching query term
  const formatCommonNames = (commonNamesStr: string, searchQuery: string) => {
    // Split by semicolons and trim whitespace
    const names = commonNamesStr.split(';').map(name => name.trim()).filter(Boolean);
    
    // If there's only one name or no names, return it directly
    if (names.length <= 1) return names[0] || commonNamesStr;
    
    // Try to find a name that matches the search query
    const lowerQuery = searchQuery.toLowerCase();
    const matchingName = names.find(name => 
      name.toLowerCase().includes(lowerQuery)
    );
    
    // If we found a matching name, show that one first
    if (matchingName) {
      return `${matchingName} +${names.length - 1} more`;
    }
    
    // Otherwise show the first name with a count
    return `${names[0]} +${names.length - 1} more`;
  };
  
  // Get all common names for display
  const getAllCommonNames = (commonNamesStr: string, searchQuery: string) => {
    // Split by semicolons, trim whitespace, and filter out empty strings
    const names = commonNamesStr.split(';').map(name => name.trim()).filter(Boolean);
    
    // If there's only one name or no valid names, just return the original string
    if (names.length <= 1) return names;
    
    // Try to prioritize matching names by sorting them
    const lowerQuery = searchQuery.toLowerCase();
    return names.sort((a, b) => {
      const aContainsQuery = a.toLowerCase().includes(lowerQuery);
      const bContainsQuery = b.toLowerCase().includes(lowerQuery);
      
      if (aContainsQuery && !bContainsQuery) return -1;
      if (!aContainsQuery && bContainsQuery) return 1;
      return 0;
    });
  };
  
  // Ensure suggestions is an array before filtering
  const validSuggestions = Array.isArray(suggestions) ? suggestions : [];
  
  // Separate common name and scientific name matches
  const commonNameMatches = validSuggestions.filter(item => {
    if (!item || !item.common_name) return false;

    // Ensure common_name is a string before calling string methods
    const commonName = String(item.common_name);

    // If we have multiple common names (separated by semicolons), check each one
    if (commonName.includes(';')) {
      const names = commonName.split(';').map(n => n.trim().toLowerCase());
      return names.some(name => name.includes(query.toLowerCase()));
    }

    // Otherwise just check the single common name
    return commonName.toLowerCase().includes(query.toLowerCase());
  });
  
  // Use species_scientific_name field as primary scientific name with fallback to species
  const scientificNameMatches = validSuggestions.filter(item => {
    // First check the new field, then fall back to the legacy field
    const scientificName = item?.species_scientific_name || item?.species;
    return scientificName?.toLowerCase().includes(query.toLowerCase());
  });

  // Update URL with search query
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      if (query.trim()) {
        router.push(`/search?q=${encodeURIComponent(query.trim())}`);
      } else {
        router.push('/search');
      }
    }, 300);
  
    return () => clearTimeout(delayDebounceFn);
  }, [query, router]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    } else {
      router.push('/search');
    }
  };

  const handleSuggestionClick = (suggestion: Suggestion) => {
    // Clear the force keep open state since we're navigating away
    setForceKeepOpen(false);
    
    // Navigate directly to the species page when clicking a suggestion
    router.push(`/species/${suggestion.taxon_id}`);
  };

  // Check if we have any suggestions to show
  const hasCommonNameMatches = commonNameMatches.length > 0;
  const hasScientificNameMatches = scientificNameMatches.length > 0;

  return (
    <div className="relative z-10 mb-16">
      <form onSubmit={handleSubmit} className="flex gap-2" data-tour="search-form">
        <div className="max-w-2xl mx-auto w-full relative">
          <div className="relative">
            <input
              data-tour="search-input"
              type="text"
              placeholder={placeholder}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                // If text is deleted, we can allow the dropdown to close
                if (!e.target.value) {
                  setForceKeepOpen(false);
                }
              }}
              onFocus={() => setIsFocused(true)}
              onBlur={(e) => {
                // Only blur if clicking outside the dropdown completely
                // Use a timeout to allow click events on dropdown items to register first
                setTimeout(() => {
                  // Don't close if we're actively keeping it open
                  if (!keepDropdownOpen) {
                    setIsFocused(false);
                  }
                }, 200);
              }}
              className="w-full flex-grow px-6 py-4 rounded-xl bg-black/30 backdrop-blur-md border-2 border-emerald-500/30 text-silvi-mint placeholder-silvi-mint/70 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-400/50 outline-none shadow-[0_0_15px_rgba(52,211,153,0.15)] transition-all duration-300 hover:border-emerald-400/40 hover:shadow-[0_0_20px_rgba(52,211,153,0.25)]"
            />
            <button 
              type="submit"
              className="absolute right-4 top-1/2 -translate-y-1/2 p-2 rounded-full hover:bg-emerald-500/20 transition-colors"
            >
              <Search className={`w-6 h-6 ${isLoading ? 'text-emerald-300' : 'text-emerald-400/80 hover:text-emerald-300'}`} />
            </button>
          </div>

          {/* Enhanced suggestions dropdown with loading state */}
          {(isFocused || keepDropdownOpen) && query.length >= 2 && (
            <div 
              className="absolute top-full mt-1 w-full bg-black/30 backdrop-blur-md rounded-xl shadow-lg max-h-96 overflow-auto z-20 border border-white/20"
              onClick={() => setForceKeepOpen(true)}
              onMouseDown={(e) => {
                // Prevent default to avoid triggering the onBlur event of the input
                e.preventDefault();
                setForceKeepOpen(true);
              }}
            >
              {isLoading ? (
                <div className="flex items-center justify-center p-8">
                  <Loader2 className="w-6 h-6 animate-spin text-emerald-300 mr-2" />
                  <span className="text-white/70">Loading...</span>
                </div>
              ) : (hasCommonNameMatches || hasScientificNameMatches) ? (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-white/10">
                    {/* Common Name column */}
                    <div>
                      <div className="px-4 py-3 font-semibold text-sm bg-black/40 backdrop-blur-md text-emerald-300 border-b border-white/10">
                        Common Names
                      </div>
                      {hasCommonNameMatches ? (
                        <div className="grid gap-2 p-2">
                          {commonNameMatches.map((suggestion, index) => {
                            const cardKey = `common-${index}`;
                            const isExpanded = expandedCards[cardKey] || false;
                            const commonName = suggestion.common_name || '';
                            const hasMultipleNames = commonName.includes(';');
                            const allCommonNames = hasMultipleNames ?
                              getAllCommonNames(commonName, query) :
                              [commonName];
                            
                            return (
                              <div 
                                key={cardKey}
                                className="p-3 rounded-lg bg-black/25 backdrop-blur-md hover:bg-black/35 cursor-pointer border border-white/10 transition-colors group"
                                onClick={() => handleSuggestionClick(suggestion)}
                              >
                                <div className="flex justify-between items-start">
                                  <div className="font-medium text-white group-hover:text-emerald-300 transition-colors">
                                    {/* Show prioritized matching name */}
                                    {hasMultipleNames ? formatCommonNames(commonName, query) : commonName}
                                  </div>
                                  <div className="flex items-center">
                                    {/* Expand/collapse button - only show if multiple names */}
                                    {hasMultipleNames && (
                                      <button
                                        onClick={(e) => toggleCardExpansion(cardKey, e)}
                                        className="mr-2 p-1 rounded-full hover:bg-white/20 transition-colors focus:outline-none"
                                        aria-label={isExpanded ? "Collapse" : "Expand"}
                                        title={isExpanded ? "Collapse" : "View all common names"}
                                      >
                                        {isExpanded ? (
                                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/70 hover:text-emerald-300">
                                            <path d="m18 15-6-6-6 6"/>
                                          </svg>
                                        ) : (
                                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/70 hover:text-emerald-300">
                                            <path d="m6 9 6 6 6-6"/>
                                          </svg>
                                        )}
                                      </button>
                                    )}
                                    <ArrowRight className="h-5 w-5 text-white/0 group-hover:text-emerald-300 transition-all" />
                                  </div>
                                </div>
                                
                                {/* Scientific name */}
                                <div className="text-xs text-white/70 italic mt-1">
                                  {suggestion.species_scientific_name || suggestion.species}
                                </div>
                                
                                {/* Expanded view of all common names */}
                                {isExpanded && hasMultipleNames && (
                                  <div className="mt-2 pt-2 border-t border-white/10 text-sm">
                                    <div className="font-medium text-emerald-300/80 text-xs mb-1">All Common Names:</div>
                                    <ul className="space-y-1">
                                      {allCommonNames.map((name, nameIndex) => (
                                        <li 
                                          key={nameIndex}
                                          className="text-white/80 pl-2 border-l-2 border-emerald-700/30"
                                        >
                                          {name}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="px-4 py-6 text-center">
                          <div className="flex justify-center mb-2">
                            <Leaf className="h-6 w-6 text-white/20" />
                          </div>
                          <p className="text-sm text-white/50">
                            No common name matches
                          </p>
                        </div>
                      )}
                    </div>
                    
                    {/* Scientific Name column */}
                    <div>
                      <div className="px-4 py-3 font-semibold text-sm bg-black/40 backdrop-blur-md text-emerald-300 border-b border-white/10">
                        Scientific Names
                      </div>
                      {hasScientificNameMatches ? (
                        <div className="grid gap-2 p-2">
                          {scientificNameMatches.map((suggestion, index) => {
                            const cardKey = `scientific-${index}`;
                            const isExpanded = expandedCards[cardKey] || false;
                            const commonName = suggestion.common_name || '';
                            const hasMultipleNames = commonName.includes(';');
                            const allCommonNames = hasMultipleNames ?
                              getAllCommonNames(commonName, query) :
                              [commonName];
                            
                            return (
                              <div 
                                key={cardKey}
                                className="p-3 rounded-lg bg-black/25 backdrop-blur-md hover:bg-black/35 cursor-pointer border border-white/10 transition-colors group"
                                onClick={() => handleSuggestionClick(suggestion)}
                              >
                                <div className="flex justify-between items-start">
                                  <div className="font-medium italic text-white group-hover:text-emerald-300 transition-colors">
                                    {suggestion.species_scientific_name || suggestion.species}
                                  </div>
                                  <div className="flex items-center">
                                    {/* Expand/collapse button - only show if multiple names */}
                                    {hasMultipleNames && (
                                      <button
                                        onClick={(e) => toggleCardExpansion(cardKey, e)}
                                        className="mr-2 p-1 rounded-full hover:bg-white/20 transition-colors focus:outline-none"
                                        aria-label={isExpanded ? "Collapse" : "Expand"}
                                        title={isExpanded ? "Collapse" : "View all common names"}
                                      >
                                        {isExpanded ? (
                                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/70 hover:text-emerald-300">
                                            <path d="m18 15-6-6-6 6"/>
                                          </svg>
                                        ) : (
                                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/70 hover:text-emerald-300">
                                            <path d="m6 9 6 6 6-6"/>
                                          </svg>
                                        )}
                                      </button>
                                    )}
                                    <ArrowRight className="h-5 w-5 text-white/0 group-hover:text-emerald-300 transition-all" />
                                  </div>
                                </div>
                                
                                {/* Common name preview */}
                                <div className="text-xs text-white/70 mt-1">
                                  {hasMultipleNames ? formatCommonNames(commonName, query) : commonName}
                                </div>
                                
                                {/* Expanded view of all common names */}
                                {isExpanded && hasMultipleNames && (
                                  <div className="mt-2 pt-2 border-t border-white/10 text-sm">
                                    <div className="font-medium text-emerald-300/80 text-xs mb-1">All Common Names:</div>
                                    <ul className="space-y-1">
                                      {allCommonNames.map((name, nameIndex) => (
                                        <li 
                                          key={nameIndex}
                                          className="text-white/80 pl-2 border-l-2 border-emerald-700/30"
                                        >
                                          {name}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="px-4 py-6 text-center">
                          <div className="flex justify-center mb-2">
                            <Leaf className="h-6 w-6 text-white/20" />
                          </div>
                          <p className="text-sm text-white/50">
                            No scientific name matches
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="p-3 border-t border-white/10 text-xs text-center text-white/50 bg-black/40 backdrop-blur-md">
                    Click a result to view detailed species information
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center p-8">
                  <Leaf className="w-6 h-6 text-emerald-300/50 mb-2" />
                  <span className="text-white/70">No matching species found</span>
                  <div className="text-xs text-white/50 mt-2">
                    Received {validSuggestions.length} suggestions, but none matched "{query}"
                  </div>
                  {/* Debug: Show what we got from the API */}
                  {process.env.NODE_ENV === 'development' && (
                    <details className="mt-3 text-xs text-left w-full max-w-xs">
                      <summary className="text-white/50 cursor-pointer">Debug info</summary>
                      <pre className="mt-2 p-2 bg-black/30 rounded text-white/70 overflow-auto max-h-32">
                        {JSON.stringify(validSuggestions.slice(0, 2), null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </form>
      {query.length >= 1 && query.length < 2 && (
        <p className="text-xs text-white/70 text-center mt-2">
          Type at least 2 characters to search
        </p>
      )}
    </div>
  );
}