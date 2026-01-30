# OK.md - Documentation Update Workflow

**Purpose**: Mid-session command to update documentation following proper SOP. Invoke with `@OK.md` when work is complete or at logical checkpoints.

---

## Two-Tier Documentation Strategy

### Tier 1: Core Docs (Concise, Surgical)

**Files**: `README.md`, `ACTIVE.md`, `TODO.md`, `CHANGELOG.md`

**Style**: Telegraphic. Omit articles (a, an, the). Maximum information density. No redundancy.

**Why**: Loaded at START of every session via GO.md. Verbosity wastes context tokens.

| Doc | Purpose | Update Frequency |
|-----|---------|------------------|
| README.md | Architecture overview, capabilities | Rare (major features only) |
| ACTIVE.md | Current production status, services, endpoints, metrics | When infra/API changes |
| TODO.md | Active tasks, planning links | Remove completed, add new |
| CHANGELOG.md | Historical record with file references | Every completed feature |

### Tier 2: Planning & Reference Docs (Detailed, Comprehensive)

**Planning**: `docs/todo/*.md` → `docs/completed/*.md` when done

**Reference**: `docs/*.md` (RECOMMENDATION_SERVICE, LEAF_INTEGRATION_GUIDE, etc.)

**API**: `API.md`, `PUBLIC_API_GUIDE.md`, `SPECIES_FIELDS_FRONTEND_GUIDE.md`

**Style**: Thorough. Include examples, edge cases, implementation details.

**Why**: Only loaded when relevant. Full context prevents mistakes.

---

## SOP Checklist

When completing a feature or fix, execute in order:

### 1. Planning Doc Lifecycle
```
IF planning doc exists in docs/todo/:
  - Update status, mark completed phases with [x]
  - IF all phases complete → Move to docs/completed/
  - Reference in CHANGELOG entry
```

### 2. TODO.md Updates
```
- REMOVE fully completed sections entirely (don't mark ✅ and leave bloated)
- UPDATE in-progress sections with new status/checkmarks
- Add new tasks discovered during implementation
```

### 3. CHANGELOG.md Entry
```markdown
## YYYY-MM-DD - Feature Name

**Planning Doc**: [docs/todo/FEATURE.md](docs/todo/FEATURE.md) OR [docs/completed/FEATURE.md](docs/completed/FEATURE.md)

**Section Name** (`file.py:line-range`):
- Bullet points, telegraphic style
- Include file references
- Technical accuracy over prose
```

### 4. ACTIVE.md Updates
```
IF work added/changed:
  - New API endpoints → Add to API Endpoints Overview
  - New database tables → Add to Database metrics
  - New services → Add to Services Status
  - Infrastructure changes → Update relevant sections
```

### 5. API.md / PUBLIC_API_GUIDE.md (if applicable)
```
IF new API endpoints added:
  - Document in API.md (full internal reference)
  - Document in PUBLIC_API_GUIDE.md (if public-facing)
```

---

## Style Guide Quick Reference

### CHANGELOG.md (Telegraphic)
```markdown
Good: `GET /api/guides/ecoregion/:eco_id` - Returns LEAF-ranked species + synthesized content
Bad: Added a new endpoint called GET /api/guides/ecoregion/:eco_id which returns the LEAF-ranked species list and any synthesized guide content for a given ecoregion
```

### TODO.md (Status Markers)
```markdown
## [IN PROGRESS] - Feature Name     # Active work
## [COMPLETE] - Feature Name ✅     # Just finished, cleanup pending
## [FUTURE] - Feature Name          # Backlog/planned
```

### Planning Docs (Phase Checkboxes)
```markdown
### Phase 1: Research
- [x] Task completed
- [ ] Task pending
```

---

## File Location Reference

```
/root/silvi-open/treekipedia/
├── README.md              # Core: Architecture overview
├── ACTIVE.md              # Core: Production status, endpoints, metrics
├── TODO.md                # Core: Active tasks, planning links
├── CHANGELOG.md           # Core: Historical record
├── GO.md                  # Onboarding procedure
├── OK.md                  # This file - doc update workflow
├── CLAUDE.md              # Development workflow
│
├── docs/
│   ├── todo/              # Planning docs for active work
│   ├── completed/         # Archived planning docs
│   ├── RECOMMENDATION_SERVICE.md
│   ├── LEAF_INTEGRATION_GUIDE.md
│   ├── SPECIES_NATIVE_STATUS_ROADMAP.md
│   └── ...
│
├── API.md                 # Full API documentation
├── PUBLIC_API_GUIDE.md    # External API access guide
├── SPECIES_FIELDS_FRONTEND_GUIDE.md  # v10 field reference
│
├── backend/               # Node.js + Express
├── frontend/              # Next.js 15 + TypeScript
├── database/              # SQL migrations
└── scripts/               # Utility scripts
```

---

## Example Invocation

User: `@OK.md` or "update docs"

Claude should:
1. Check if planning doc exists → update or move to completed
2. Update in-progress section in TODO.md (or remove if fully complete)
3. Add CHANGELOG entry (telegraphic, with planning doc link)
4. Update ACTIVE.md with new endpoints/metrics
5. Update API.md if new endpoints added

---

**Remember**: Core docs are "hot" (read every session). Planning/reference docs are "cold" (read on-demand). Hot = efficient. Cold = complete.
