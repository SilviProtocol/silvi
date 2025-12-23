# Treekipedia

**Tree Intelligence Commons** - A decentralized, open-source knowledge repository for tree species data, powered by AI and blockchain technology.

---

## Quick Links

| Document | Purpose |
|----------|---------|
| [GO.md](GO.md) | **Start here** - Onboarding workflow |
| [ACTIVE.md](ACTIVE.md) | Current production status |
| [TODO.md](TODO.md) | Development roadmap |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [CLAUDE.md](CLAUDE.md) | Development guide |
| [API.md](API.md) | API documentation |

---

## Overview

Treekipedia is an open-source platform making tree species data accessible, verifiable, and incentivized. Developed by [Silvi Protocol](https://silvi.earth), it combines AI-driven research with blockchain transparency to support reforestation, ecological restoration, and biodiversity monitoring.

### Current Stats
- **67,927 species** with 130 data fields each (50,797 species + 16,946 subspecies)
- **31,796 images** across 13,609 species
- **5.3M geohash tiles** with 89M species occurrences
- **847 WWF ecoregions** for ecological context
- **Primary keys**: `taxon_id` + `taxon_full` (suffix `-00` = species, `-01`+ = subspecies)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  Next.js 15 + React 18 + TypeScript + Tailwind + Wagmi v2       │
│  https://treekipedia.silvi.earth (Vercel)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND API                              │
│  Node.js + Express + PostgreSQL/PostGIS                          │
│  https://treekipedia-api.silvi.earth (PM2, port 3000)           │
├─────────────────────────────────────────────────────────────────┤
│  Controllers: species, geospatial, research, sponsorship        │
│  Services: AI research, blockchain, IPFS, research queue        │
│  Middleware: API auth, rate limiting                            │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   PostgreSQL    │ │   Knowledge     │ │   Blockchain    │
│   + PostGIS     │ │   Graph         │ │   (Multi-chain) │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ 67,927 species  │ │ Blazegraph:9999 │ │ Celo            │
│ 5.3M geohash    │ │ Fuseki:3030     │ │ Base            │
│ 847 ecoregions  │ │ Ontology:8000   │ │ Optimism        │
└─────────────────┘ └─────────────────┘ │ Arbitrum        │
                                        └─────────────────┘
                                                │
                                                ▼
                                   ┌─────────────────────┐
                                   │    IPFS Storage     │
                                   │    (Lighthouse)     │
                                   │    EAS Attestations │
                                   └─────────────────────┘
```

---

## Codebase Structure

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| **frontend/** | Next.js app | `app/`, `components/`, `lib/types.ts` |
| **backend/** | Express API | `server.js`, `controllers/`, `services/` |
| **contracts/** | Solidity (Hardhat) | `contracts/ContreebutionNFT.sol` |
| **database/** | SQL schemas | `current-schema.sql`, migrations |
| **scripts/** | Utilities | Import scripts, data processing |

---

## Tech Stack

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 15.2.3 | React framework |
| React | 18.3.1 | UI library |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 3.x | Styling |
| Wagmi | v2 | Wallet integration |
| React-Leaflet | - | Maps |

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Node.js | 18+ | Runtime |
| Express | 4.x | API framework |
| PostgreSQL | 14+ | Database |
| PostGIS | 3.2 | Spatial queries |
| PM2 | - | Process management |

### Blockchain
| Chain | Purpose |
|-------|---------|
| Celo | Primary NFT minting |
| Base | L2 support |
| Optimism | L2 support |
| Arbitrum | L2 support |

---

## Key Features

1. **Species Search** - 67,927 species searchable with subspecies discovery
2. **Geospatial Analysis** - Polygon-based species analysis with PostGIS
3. **AI Research** - OpenAI/Perplexity-powered data generation
4. **Contreebution NFTs** - Blockchain-verified research contributions
5. **Ecoregion Integration** - 847 WWF ecoregions for ecological context
6. **Native Status Analysis** - Country-based native/introduced classification
7. **Image Database** - 31,796 Wikimedia Commons images with attribution

---

## Getting Started

```bash
# Clone repository
git clone https://github.com/silvi-protocol/treekipedia.git
cd treekipedia

# Set up environment
cp .env.example .env
# Edit .env with your credentials

# Install dependencies
cd frontend && yarn install
cd ../backend && yarn install

# Run development servers
cd backend && nodemon server.js  # API on port 3000
cd frontend && yarn dev          # Frontend on port 3001
```

See [CLAUDE.md](CLAUDE.md) for detailed development commands.

---

## Documentation

| Document | Description |
|----------|-------------|
| **[GO.md](GO.md)** | Onboarding workflow - start here for Claude Code |
| **[ACTIVE.md](ACTIVE.md)** | Current production status and metrics |
| **[TODO.md](TODO.md)** | Development roadmap and tasks |
| **[CHANGELOG.md](CHANGELOG.md)** | History of completed features |
| **[CLAUDE.md](CLAUDE.md)** | Development guide and patterns |
| **[API.md](API.md)** | Comprehensive API documentation |
| **[SPECIES_FIELDS_FRONTEND_GUIDE.md](SPECIES_FIELDS_FRONTEND_GUIDE.md)** | v10 field reference |

---

## License

MIT License - see [LICENSE.md](LICENSE.md)

---

## Silvi Protocol

Treekipedia is developed and maintained by **Silvi**, a blockchain-powered reforestation protocol. It serves as the authoritative species database within the Silvi App, supporting Payments for Ecosystem Services (PES) and MRV (Monitoring, Reporting, Verification).

**Links**:
- Website: [silvi.earth](https://silvi.earth)
- Treekipedia: [treekipedia.silvi.earth](https://treekipedia.silvi.earth)
- API: [treekipedia-api.silvi.earth](https://treekipedia-api.silvi.earth)
