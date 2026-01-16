# Species Research Command

Process the Treekipedia research queue using the ATOMIC insight model.

## Instructions

1. First, read the skill file at `.claude/skills/species-research/SKILL.md` to understand the full workflow and ATOMIC insight model requirements.

2. Then execute the workflow:
   - GET http://localhost:5003/queue/next to get next species
   - POST http://localhost:5003/queue/{queue_id}/start to mark as processing
   - Conduct comprehensive web searches for all 35 fields
   - Generate **ATOMIC insights** (multiple insights per field for multi-insight fields like cultural_significance, tolerances, habitat)
   - POST http://localhost:5003/research/{taxon_id}/save with all insights
   - POST http://localhost:5003/queue/{queue_id}/complete
   - Loop until queue is empty

## CRITICAL: ATOMIC MODEL

**You MUST generate 50-80+ total insights per species.** If you only have ~35 insights (one per field), you are doing it WRONG.

Multi-insight fields (generate MULTIPLE insights, one per distinct fact):
- `cultural_significance` - One per culture/tradition
- `tolerances` - One per tolerance type
- `habitat` - One per habitat type
- `ecological_function` - One per ecosystem service
- `non_timber_products` - One per product
- `disease_pest_management` - One per disease/pest

Read the full SKILL.md for complete instructions.
