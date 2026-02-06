# GO.md - Claude Code Onboarding Procedure

**Purpose**: Standard onboarding protocol for fresh Claude Code instances working on Treekipedia.

---

## Onboarding Checklist

When a user says "read GO.md", "go", or similar, follow this procedure:

### Step 1: Check Services Status

```bash
# Quick status check
lsof -ti:5001 && echo "Backend: Running" || echo "Backend: Stopped"
lsof -ti:5002 && echo "Location Predictor: Running" || echo "Location Predictor: Stopped"
lsof -ti:3001 && echo "Frontend: Running" || echo "Frontend: Stopped"
brew services list | grep postgresql
```

### Step 2: Read Core Documentation (in order)

Read these files to understand the project:

1. **[README.md](../../treekipedia/README.md)** - Architecture and overview
2. **[ACTIVE.md](ACTIVE.md)** - Current production status and operational reference (same folder)
3. **[TODO.md](TODO.md)** - Current tasks and development roadmap (same folder)
4. **[CHANGELOG.md](CHANGELOG.md)** - History of features and improvements (same folder)

### Step 3: Provide Brief Assessment

After reading all files, provide a **brief assessment** (1-2 paragraphs) covering:

- **Production Status**: Current system health, key metrics
- **Recent Progress**: Last 1-2 major completions from CHANGELOG.md
- **Current Focus**: What's in progress or next priority from TODO.md
- **Architecture State**: Any notable technical details or blockers

Keep it concise - this is a "state of the union" snapshot, not a detailed report.

### Step 4: Ask What To Work On

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
- Update service commands if ports or processes changed

---

## Common Pitfalls

**Development Environment**:
- DON'T use port 5000 for backend (macOS ControlCenter conflict)
- DO use port 5001 for backend, 5002 for Python services, 3001 for frontend

**Port 5002 Service Conflict**:
- DON'T run both `location_predictor_FIXED.py` and `api_only.py` simultaneously
- DO use `location_predictor_FIXED.py` for habitat prediction features
- DO use `api_only.py` only for GraphFlow/ontology generation

**Database**:
- DON'T modify production database without backup
- DO use local PostgreSQL for development (67,743 species synced)

**Git**:
- DON'T commit API keys or credentials
- DO use `.env` files for sensitive configuration

---

## Quick Reference

**Project Type**: Open-source AI-powered tree species knowledge repository

**Architecture**:
- Next.js 15 frontend (React 18, TypeScript, Tailwind)
- Express.js backend (Node.js, PostgreSQL 17 + PostGIS 3.6)
- Python microservices (AlphaEarth GEE sampling, GraphFlow ontology)
- Blockchain integration (Base, Celo, Optimism, Arbitrum)

**Current Phase**:
- AlphaEarth habitat prediction feature complete (100 species POC)
- GraphFlow admin UI integrated
- Analysis map with heatmap and multi-layer support

**Key Technologies**:
- PostgreSQL 17 with PostGIS 3.6 (67,743 species, 5.7M geohash tiles)
- Google Earth Engine (AlphaEarth satellite embeddings)
- BigQuery (embedding storage)
- React Query, Wagmi, Leaflet

**Local Ports**:
| Service | Port | Start Command |
|---------|------|---------------|
| Backend API | 5001 | `node server.js` |
| Location Predictor | 5002 | `python3 location_predictor_FIXED.py` |
| Frontend | 3001 | `npm run dev` |
| PostgreSQL | 5432 | `brew services start postgresql@17` |

---

## Quick Start Commands

```bash
# Start all services
./start-local.sh

# Stop all services
./stop-local.sh

# Or manually:
cd treekipedia/backend && node server.js &
cd orchestrator && python3 location_predictor_FIXED.py &
cd treekipedia/frontend && npm run dev &
```

---

**When in doubt, refer back to this file or ask the user for clarification.**

**Documentation Structure** (all in `.claude/project-management/` except CLAUDE.md):
- **GO.md** - This file (onboarding)
- **ACTIVE.md** - Current system status
- **TODO.md** - Task roadmap
- **CHANGELOG.md** - History
- **CLAUDE.md** - Development guide (in `.claude/`)
- **README.md** - Architecture overview (in `treekipedia/`)
