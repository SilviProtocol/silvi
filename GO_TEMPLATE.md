# GO_TEMPLATE.md - Claude Code Documentation System Template

**Purpose**: A reusable template for creating a documentation workflow system that enables Claude Code to onboard instantly to any codebase.

---

## Overview

This system uses **5 documentation files** working together:

| File | Purpose | Updates |
|------|---------|---------|
| **GO.md** | Onboarding workflow - the entry point | Rarely (workflow changes only) |
| **CLAUDE.md** | Development guide for Claude Code | When patterns/rules change |
| **README.md** | Architecture overview | When architecture changes |
| **ACTIVE.md** | Current production status | Frequently (can be auto-updated) |
| **TODO.md** | Forward-looking tasks | Constantly (as work progresses) |
| **CHANGELOG.md** | History of completed work | After each significant completion |

**The Key Insight**: When you say "read GO.md" (or similar), Claude Code follows a structured onboarding procedure that reads all context files in order, synthesizes understanding, and asks what to work on.

---

## File Templates

### 1. GO.md - The Onboarding Workflow

```markdown
# GO.md - Claude Code Onboarding Procedure

**Purpose**: Standard onboarding protocol for fresh Claude Code instances working on [PROJECT_NAME].

---

## Onboarding Checklist

When a user says "read GO.md" or similar, follow this procedure:

### Step 1: [Optional] Run Status Check Script

If your project has automated status checking:

\`\`\`bash
# Example: Get fresh metrics and auto-update documentation
python scripts/status_check.py --update
\`\`\`

This will:
- Query current system metrics
- Auto-update ACTIVE.md with current stats
- [Add project-specific status checks here]

Use these **real-time numbers** in your assessment instead of relying on potentially outdated documentation.

### Step 2: Read Core Documentation (in order)

Read these files to understand the project:

1. **README.md** - Architecture and overview
2. **ACTIVE.md** - Current production status and operational reference
3. **TODO.md** - Current tasks and development roadmap
4. **CHANGELOG.md** - History of features and improvements

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

- Run status check script (if available) to auto-update metrics
- Update service status, endpoints, or configuration as needed

---

## Common Pitfalls

[Add project-specific pitfalls here, e.g.:]
- DON'T [common mistake]
- DO [correct approach]

---

## Quick Reference

**Project Type**: [One-line description]
**Architecture**: [High-level architecture pattern]
**Current Phase**: [What phase of development]

**Key Technologies**:
- [Tech 1]
- [Tech 2]
- [Tech 3]

---

**When in doubt, refer back to this file or ask the user for clarification.**
```

---

### 2. CLAUDE.md - Development Guide

```markdown
# [PROJECT_NAME] Development Guide

**For onboarding**: Read `GO.md` first for complete project context.
**For architecture**: See `README.md`
**For current status**: See `ACTIVE.md`

This guide covers development workflow, code patterns, and critical rules.

---

## Essential Commands

### Environment Setup
\`\`\`bash
# [Project-specific setup commands]
\`\`\`

### Development Commands
\`\`\`bash
# [Build, test, run commands]
\`\`\`

### Process Management
\`\`\`bash
# [Service management commands if applicable]
\`\`\`

---

## Development Guidelines

### Code Style
- [Import order conventions]
- [Naming conventions]
- [Indentation/formatting]
- [Type hints/documentation]
- [Error handling patterns]

### Documentation Style

**CHANGELOG.md - Telegraphic Style**:
- Omit articles (a, an, the) and conjunctions where possible
- Maintain specificity: include file references, error details, technical accuracy
- Target 3-8 lines per entry for recent work, 1-3 lines for older entries

### [Project-Specific Patterns]

[Add sections for important patterns like:]
- Database access patterns
- API patterns
- State management
- Logging conventions

---

## CRITICAL RULES

### Security Requirements
[Add security rules specific to your project]

### [Other Critical Rules]
[Add project-specific non-negotiable rules]

---

## Troubleshooting

### Common Issues
- [Issue 1]: [Solution]
- [Issue 2]: [Solution]

### Log Files
- [Where to find logs]

---

## Documentation Structure

- **GO.md** - Start here for onboarding procedure
- **README.md** - Architecture overview
- **ACTIVE.md** - Current production status
- **TODO.md** - Current tasks and roadmap
- **CHANGELOG.md** - History of features and improvements
- **CLAUDE.md** - This file - development workflow and patterns

## Documentation Quick Reference by Topic

| Issue Type | Primary Documentation |
|------------|----------------------|
| [Topic 1] | [Relevant file/section] |
| [Topic 2] | [Relevant file/section] |

---

**Remember**: [Project name and key context reminder]
```

---

### 3. README.md - Architecture Overview

```markdown
# [PROJECT_NAME]

**[Tagline or one-sentence description]**

[2-3 paragraph overview of what this project does and why it exists]

---

## Architecture Overview

[High-level architecture description]

\`\`\`
[ASCII diagram of system architecture]
\`\`\`

### Core Components

**[Component 1]** - [Brief description]
- [Key feature]
- [Key feature]

**[Component 2]** - [Brief description]
- [Key feature]
- [Key feature]

---

## Codebase Structure

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| **dir1/** | [Purpose] | [Key files] |
| **dir2/** | [Purpose] | [Key files] |

---

## Tech Stack

### [Category 1]
| Technology | Version | Purpose |
|------------|---------|---------|
| **Tech** | X.X | [Purpose] |

### [Category 2]
| Technology | Version | Purpose |
|------------|---------|---------|
| **Tech** | X.X | [Purpose] |

---

## Getting Started

[Quick start instructions]

---

## Documentation

- **[ACTIVE.md](ACTIVE.md)** - Current production status
- **[TODO.md](TODO.md)** - Development roadmap
- **[CHANGELOG.md](CHANGELOG.md)** - Version history
```

---

### 4. ACTIVE.md - Current Production Status

```markdown
# ACTIVE - [PROJECT_NAME] System Status

**Last Updated**: [Date/timestamp]
**System Health**: [Status indicator]

## Live Metrics

[Key metrics that change frequently - can be auto-updated by scripts]

### [Metric Category 1]
- **Metric A**: [Value]
- **Metric B**: [Value]

### [Metric Category 2]
- **Metric A**: [Value]
- **Metric B**: [Value]

---

## System Resources

### Services
| Service | Status | Purpose |
|---------|--------|---------|
| [Service 1] | [Status] | [Purpose] |

### Infrastructure
- **[Resource 1]**: [Status/value]
- **[Resource 2]**: [Status/value]

---

## API Endpoints

[If applicable - list key endpoints]

### [Category]
- `METHOD /path` - [Description]

---

## Current Capabilities

### [Feature Area 1]
- [Capability]
- [Capability]

### [Feature Area 2]
- [Capability]
- [Capability]

---

## Quick Commands

\`\`\`bash
# [Common operational commands]
\`\`\`

---

## Configuration Reference

[If applicable - database schema, config structure, etc.]

---

## Documentation References

- **GO.md** - Onboarding procedure
- **README.md** - Architecture overview
- **TODO.md** - Development roadmap
- **CHANGELOG.md** - Version history
```

---

### 5. TODO.md - Development Roadmap

```markdown
# TODO.md - [PROJECT_NAME] Implementation Plan

Active tasks and planned work. See CHANGELOG.md for completed features.

---

## [IN PROGRESS] - [Feature/Task Name]

**Status**: [Current status]

### [Phase/Section]
- [ ] Task 1
- [ ] Task 2
- [x] Completed task

### [Next Phase]
- [ ] Task 1
- [ ] Task 2

---

## [HIGH PRIORITY] - [Feature/Task Name]

**Status**: [Status description]

- [ ] Task 1
- [ ] Task 2

---

## [MEDIUM PRIORITY] - [Feature/Task Name]

**Status**: [Status description]

- [ ] Task 1
- [ ] Task 2

---

## [LOW PRIORITY / FUTURE] - [Feature/Task Name]

- [ ] Task 1
- [ ] Task 2

---

## Documentation References

- **GO.md** - Onboarding procedure
- **ACTIVE.md** - Current system status
- **CHANGELOG.md** - Completed features
- **README.md** - Architecture overview
```

---

### 6. CHANGELOG.md - Version History

```markdown
# CHANGELOG - [PROJECT_NAME]

Complete history of features, fixes, and improvements. For current status see ACTIVE.md, upcoming work see TODO.md.

**WRITING STYLE**: Use telegraphic style for all entries. Omit articles (a, an, the), conjunctions where possible. Maintain specificity: include file references, error details, technical accuracy. Target 3-8 lines per entry for recent work, 1-3 lines for older entries.

---

## YYYY-MM-DD - [Brief Title]

**[Category]** - [One-line summary]
- [Specific change with file reference]
- [Impact or result]
- Files: [modified files]

---

## YYYY-MM-DD - [Brief Title]

[Continue pattern...]

---

## Earlier History

[Compressed older entries]
```

---

## Implementation Guide

### Step 1: Create the Files

Create all 6 files in your project root:
1. `GO.md` - Copy template, customize workflow
2. `CLAUDE.md` - Add your development patterns and rules
3. `README.md` - Document your architecture
4. `ACTIVE.md` - Document current state
5. `TODO.md` - Add your tasks
6. `CHANGELOG.md` - Start history

### Step 2: Customize for Your Project

**GO.md Customizations**:
- Add/remove status check step based on whether you have automation
- Customize the assessment criteria
- Add project-specific pitfalls

**CLAUDE.md Customizations**:
- Add your essential commands
- Document your code patterns
- Add your critical rules
- Create documentation quick reference table

**ACTIVE.md Customizations**:
- Define what metrics matter for your project
- Add relevant service/infrastructure status
- Include schema/config reference if applicable

### Step 3: Optional - Create Status Check Script

If you want auto-updating metrics:

```python
# scripts/status_check.py
"""
Auto-update ACTIVE.md with current system metrics.
Run with: python scripts/status_check.py --update
"""

def get_metrics():
    """Query your system for current metrics."""
    # Database queries, API calls, system checks, etc.
    pass

def update_active_md(metrics):
    """Update ACTIVE.md header with fresh metrics."""
    # Read file, update metrics section, write back
    pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    metrics = get_metrics()
    print_status(metrics)

    if args.update:
        update_active_md(metrics)
```

### Step 4: Maintain the System

**During Development**:
- Update TODO.md in real-time as you work
- Check off items immediately when done
- Add new discovered tasks

**After Completing Work**:
- Add CHANGELOG.md entry (telegraphic style)
- Update TODO.md (remove completed, add new)
- Update ACTIVE.md if system changed

**Periodically**:
- Run status check to refresh metrics
- Review and clean up stale TODO items
- Archive old planning documents

---

## Principles

### Single Source of Truth
Each file has ONE purpose. Don't duplicate information across files.

### Forward vs Backward Looking
- TODO.md = future (what to do)
- CHANGELOG.md = past (what was done)
- ACTIVE.md = present (current state)

### Telegraphic Style
Documentation should be dense and scannable. Omit unnecessary words while preserving technical accuracy.

### Real-Time Updates
TODO.md should always reflect actual work state. Update immediately, not in batches.

### Onboarding-First Design
The system is designed so a fresh Claude Code instance can fully understand the project by following GO.md.

---

## Adapting to Different Project Types

### Web Application
- ACTIVE.md: API endpoints, deployment status, user metrics
- TODO.md: Features, bugs, tech debt
- Status check: Query database, check services

### CLI Tool
- ACTIVE.md: Supported commands, version info, installation
- TODO.md: New commands, compatibility, documentation
- Status check: May not be needed (static project)

### Library/Package
- ACTIVE.md: API reference, compatibility matrix, usage examples
- TODO.md: New features, deprecations, breaking changes
- Status check: Test suite results, coverage

### Data Pipeline
- ACTIVE.md: Pipeline stages, data freshness, error rates
- TODO.md: New sources, transformations, optimizations
- Status check: Query pipeline metrics, check job status

### Microservices
- ACTIVE.md: Service map, health status, dependencies
- TODO.md: Per-service tasks, cross-cutting concerns
- Status check: Query each service health endpoint

---

## Anti-Patterns to Avoid

1. **Don't duplicate** - If it's in README.md, don't repeat in ACTIVE.md
2. **Don't let TODO.md rot** - Stale tasks destroy trust in the system
3. **Don't skip CHANGELOG entries** - History is invaluable for context
4. **Don't make GO.md complex** - Keep it simple and sequential
5. **Don't forget to update ACTIVE.md** - Outdated status misleads

---

**This template captures a documentation philosophy, not rigid rules. Adapt it to your project's needs while preserving the core workflow: onboard → assess → ask → work → document.**
