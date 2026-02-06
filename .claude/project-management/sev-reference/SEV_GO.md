# GO.md - Claude Code Onboarding Procedure

**Purpose**: Standard onboarding protocol for fresh Claude Code instances working on Treekipedia.

---

## Onboarding Checklist

When a user says "read GO.md" or similar, follow this procedure:

### Step 1: Read Core Documentation (in order)

Read these files to understand the project:

1. **README.md** - Architecture and project overview
2. **ACTIVE.md** - Current production status and live metrics
3. **TODO.md** - Current tasks and development roadmap
4. **CHANGELOG.md** - History of completed features

### Step 2: Provide Brief Assessment

After reading all files, provide a **brief assessment** (1-2 paragraphs) covering:

- **Production Status**: Current system health, key metrics
- **Recent Progress**: Last 1-2 major completions from CHANGELOG.md
- **Current Focus**: What's in progress or next priority from TODO.md
- **Architecture State**: Any notable technical details or blockers

Keep it concise - this is a "state of the union" snapshot, not a detailed report.

### Step 3: Ask What To Work On

Present the current priorities from TODO.md and ask:

> "What would you like to work on from the TODO list? We have:
>
> [IN PROGRESS]: [current in-progress items]
>
> [HIGH PRIORITY]: [high priority items]
>
> [MEDIUM PRIORITY]: [medium priority items]
>
> Which area would you like to focus on?"

---

## During Development: Documentation Maintenance

As you work with the user, **maintain documentation discipline**:

### TODO.md Maintenance (CRITICAL)

- **Check off items** immediately when completed (don't batch)
- **Add new items** when discovering additional work
- **Move completed sections** to CHANGELOG.md when features are done
- **Update status indicators** as priorities shift

### When Work is Completed

1. **Update CHANGELOG.md**: Add entry with date and brief description
2. **Update TODO.md**: Remove/check off completed items
3. **Update ACTIVE.md**: If system status, endpoints, or infrastructure changed

### When Production Status Changes

- Update ACTIVE.md with new metrics, endpoints, or service status
- Update README.md if architecture changes significantly

---

## Common Pitfalls

- **DON'T** modify smart contracts in `/contracts` without explicit discussion - they may be outdated
- **DON'T** run curl commands directly - provide them to the user to execute
- **DON'T** commit `.env` files or any secrets
- **DO** check PM2 status before assuming backend is running
- **DO** reference the root `.env` file path correctly (`../env` from subdirs)
- **DO** test API changes against `https://treekipedia-api.silvi.earth`

---

## Quick Reference

**Project Type**: Tree species knowledge database with AI research and blockchain integration
**Architecture**: Next.js frontend + Node.js/Express backend + PostgreSQL/PostGIS + Multi-chain NFTs
**Current Phase**: V10 data migration complete, frontend refinement, geospatial analysis features

**Key Technologies**:
- **Frontend**: Next.js 15, React 18, TypeScript, Tailwind, Wagmi v2, React-Leaflet
- **Backend**: Node.js, Express, PostgreSQL, PostGIS, PM2
- **Blockchain**: Celo, Base, Optimism, Arbitrum (multi-chain NFT minting)
- **AI**: OpenAI, Perplexity API for research generation
- **Storage**: IPFS (Lighthouse), EAS attestations

**Key URLs**:
- **Frontend**: https://treekipedia.silvi.earth
- **Backend API**: https://treekipedia-api.silvi.earth
- **Ontology Service**: https://treekipedia-graph-flow.silvi.earth

**Database Stats**:
- 67,927 species (130 fields per species)
- 31,796 images across 13,609 species
- 5.3M geohash tiles with 89M occurrences
- 847 WWF ecoregions

---

## Documentation Structure

### Core System (root)
| File | Purpose | Updates |
|------|---------|---------|
| **GO.md** | Onboarding workflow (this file) | Rarely |
| **CLAUDE.md** | Development guide, commands, patterns | When patterns change |
| **README.md** | Architecture overview | When architecture changes |
| **ACTIVE.md** | Current production status | Frequently |
| **TODO.md** | Forward-looking tasks | Constantly |
| **CHANGELOG.md** | History of completed work | After each completion |

### Reference Docs (root)
- **API.md** - Comprehensive API endpoint documentation
- **SPECIES_FIELDS_FRONTEND_GUIDE.md** - v10 130-field reference for frontend

### Planning & Strategy (`docs/`)
| Directory | Purpose |
|-----------|---------|
| **docs/todo/** | Active planning documents for TODO sections |
| **docs/completed/** | Finished planning docs (moved from todo/) |
| **docs/archive/** | Obsolete/superseded documentation |
| **docs/*.md** | Strategy docs (RECOMMENDATION_SERVICE, LIGHTPAPER, etc.) |

---

**When in doubt, refer back to this file or ask the user for clarification.**
