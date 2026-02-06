# Research Comparison: Old vs Atomic Insights

This folder compares research output before and after the atomic insights architecture change.

## Key Differences

### OLD Model (Combined Insights)
- 1 insight per claim_type (35 total per species)
- All cultural significance combined into one blob
- All common names in one insight
- Hard to query individual facts

### NEW Model (Atomic Insights)
- Multiple insights per claim_type where appropriate
- Each cultural significance fact is separate
- Each common name is ranked separately
- Each fact independently sourced and scored

## Files

| File | Description |
|------|-------------|
| `ginkgo_OLD_combined_insights.json` | Original Ginkgo research (35 combined insights) |
| `fagus_OLD_combined_insights.json` | Original Fagus research (35 combined insights) |
| `ginkgo_NEW_atomic_prompt.md` | New atomic prompt for Ginkgo research |
| `ginkgo_NEW_atomic_example.json` | Example atomic output structure |

## Example Comparison

### OLD: cultural_significance (1 insight)
```json
{
  "claim_type": "cultural_significance",
  "claim_value": "Sacred in Buddhism, Taoism, Confucianism, Shinto. Buddhist monks preserved species through temple plantings. Symbol of longevity, hope, resilience, peace. Hiroshima: Six trees survived 1945 atomic bomb...",
  "confidence": 0.92
}
```

### NEW: cultural_significance (4+ insights)
```json
[
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Sacred in Buddhism - monks preserved species through temple plantings", "context": "Buddhism", "region": "East Asia"},
    "confidence": 0.95,
    "sources": [{"url": "...", "title": "Buddhist Temple Records"}]
  },
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Six trees survived 1945 Hiroshima atomic bomb, now symbols of peace", "context": "Japanese post-war", "region": "Japan"},
    "confidence": 0.98,
    "sources": [{"url": "...", "title": "Hiroshima Peace Memorial"}]
  },
  {
    "claim_type": "cultural_significance",
    "claim_value": {"text": "Symbol in Confucianism and Taoism representing longevity", "context": "Chinese philosophy", "region": "China"},
    "confidence": 0.90,
    "sources": [{"url": "...", "title": "Chinese Cultural Heritage"}]
  }
]
```

## Benefits of Atomic Model

1. **Queryable**: "Find all species sacred to Buddhism"
2. **Granular confidence**: Each fact scored independently
3. **Better citations**: Sources linked to specific claims
4. **Updatable**: Can add new facts without replacing all
5. **RDF-friendly**: Clean subject-predicate-object mapping

## Migration Status

- Database schema: ✅ Updated (`08_atomic_insights_architecture.sql`)
- Aggregation triggers: ✅ Auto-sync to species._ai columns
- Research prompts: ✅ New atomic prompts created
- RDF exporter: ✅ Lean export (facts only, no provenance bloat)
- IPFS archiver: ✅ Version snapshots

## Blocked

- Fuseki upload: Need `FUSEKI_PASSWORD`
- IPFS upload: Need `LIGHTHOUSE_API_KEY`
