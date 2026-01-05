## GPT-5 Local AI Researcher Plan

### Purpose

Design and implement a local, privacy-first deep researcher that extracts verifiable tree knowledge at scale, integrates with the existing Treekipedia stack, and supports batch prompting, staging/validation, ontology publication, and admin control — all runnable on a laptop with ~18GB RAM using a quantized local LLM.

---

## 1) High-Level Architecture

- **Local LLM Server**: LM Studio (preferred) or Ollama serving an OpenAI-compatible API on `localhost`.
- **Research Orchestrator**: 
  - Node.js integration in Treekipedia backend (`treekipedia/backend/services/aiResearch.js`, `researchQueue.js`) extended to support local models.
  - Optional Python microservice for academic ingestion and advanced scraping/function-calling.
- **Data Fetchers**: API-first (GBIF, iNaturalist, Wikipedia API) with ethical scraping fallback.
- **Structuring & Validation**: Deterministic JSON extraction with schema validation and provenance.
- **Staging Layer (Postgres)**: JSONB staging tables + citations before publishing to the canonical species tables.
- **Ontology Pipeline**: Use `ontology-generator` (OWLready2) to export RDF/OWL and (optionally) publish to Blazegraph/Jena and pin artifacts to IPFS.
- **Admin Portal (Frontend)**: Local Treekipedia admin controls for batch runs, queue monitoring, LLM provider config, error logs, and publish workflows.

```
User → Admin UI (Next.js) → Backend API (Express) → Research Queue → Providers (LM Studio/Ollama/OpenAI/Perplexity)
                                                   ↘ Staging DB (Postgres JSONB)
                                                    ↘ Ontology Generator (Python) → RDF/OWL → Blazegraph/Jena → IPFS
```

---

## 2) Local LLM Setup (18GB RAM)

### Recommended Quantized Models
- **Phi-3 Mini 3.8B (Q4)**: Strong for structured extraction, low RAM (~4–6GB).
- **Qwen2.5-1.5B (Q4)**: Fast inference, good multilingual/domain generalization (~2–3GB).
- **Gemma-2-2B (Q4)**: Good reasoning for dependencies/hosts (~3–5GB).

Run on CPU; throughput is enough for background research. Prefer Q4 quantization for stability.

### LM Studio
1) Install LM Studio and download a quantized instruct model (e.g., `phi-3-mini-4k-instruct-q4`).
2) Developer tab → Start server on `http://localhost:1234/v1`.
3) Verify with curl:
```bash
curl -s http://localhost:1234/v1/models | jq .
```

### Ollama (alternative)
```bash
brew install ollama
ollama pull qwen2.5:1.5b-instruct-q4_0
ollama serve &
```

---

## 3) Provider Abstraction in Backend

Add provider selection to Treekipedia backend so the research queue can use:
- LM Studio (OpenAI-compatible base_url)
- Ollama (via an OpenAI shim or direct REST)
- OpenAI (remote)
- Perplexity (remote) [optional]

### Environment Variables
```
RESEARCH_PROVIDER=lmstudio            # lmstudio | ollama | openai | perplexity
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=phi-3-mini-4k-instruct-q4
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:1.5b-instruct-q4_0
OPENAI_API_KEY=sk-...                 # if used
PPLX_API_KEY=...                      # if used
RESEARCH_MAX_TOKENS=2048
RESEARCH_TEMPERATURE=0.2
```

### Implementation Notes (Node)
- In `treekipedia/backend/services/aiResearch.js`:
  - Introduce a `createChatClient()` helper that returns a unified `chatCompletion({model, messages, temperature, tools?})` using `baseURL` and key depending on `RESEARCH_PROVIDER`.
  - Replace direct OpenAI calls with the adapter.
  - Keep existing parallelization logic; route Perplexity steps behind a feature flag so local mode can run air-gapped (no external calls).
- In `treekipedia/backend/services/researchQueue.js`:
  - Retain rate limiters; add per-provider cooldowns (LM Studio can handle multiple small requests but prefer sequential aspect prompts).
  - Support sub-tasks per aspect (see Section 5) to allow fine-grained retries.

---

## 4) Batch Prompting Strategy

Research per species is decomposed into aspect prompts to reduce hallucinations and allow targeted retries:
- `morphology`
- `ecology_stewardship`
- `soil_types`
- `tolerances`
- `hosts` (species supported by this tree)
- `dependencies` (pollinators/symbionts relying on this tree)

Each aspect prompt:
- Temperature 0.1–0.2; max tokens from `RESEARCH_MAX_TOKENS`.
- Strict JSON schema with minimal prose.
- Include “Only use info from provided text. If unknown, return empty list.”

Batching rules:
- Read raw sources (APIs + scraped pages) → concatenate and trim to model context.
- Run aspect prompts sequentially to avoid context bleed; cache intermediate results.
- Retry policy: 2–3 attempts per aspect; backoff on validator failures.

---

## 5) Data Sources, Fetching, and Citing

Priority: APIs → open scraping (ethically) → PDFs

- **GBIF API**: taxonomy, synonyms, distribution metadata.
- **iNaturalist API**: observations, interaction hints.
- **Wikipedia API**: summaries; as fallback, HTML scrape the page.
- **Academic PDFs**: optional; parse with `pypdf`/`pdfminer.six` in Python service.

Ethical scraping best practices:
- Check `robots.txt`; respect disallow rules.
- User-Agent: `TreekipediaResearcher/1.0 (contact@domain)`
- 1 req / 2–5s; exponential backoff on 429.
- Store full source URL and access timestamp; include snippet used for extraction.

---

## 6) Staging and Validation (Postgres)

Create staging tables for extracted JSON before publishing to canonical species rows.

### Tables
```sql
-- Staging table per species + versioned runs
CREATE TABLE IF NOT EXISTS species_research_staging (
  id BIGSERIAL PRIMARY KEY,
  taxon_id BIGINT NOT NULL,
  scientific_name TEXT NOT NULL,
  run_id UUID NOT NULL DEFAULT gen_random_uuid(),
  provider TEXT NOT NULL,
  aspects JSONB NOT NULL,      -- { morphology: {...}, hosts: [...], ... }
  citations JSONB NOT NULL,    -- [{url, title?, snippet?, accessed_at}]
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (taxon_id, run_id)
);

-- Validation issues captured for transparency
CREATE TABLE IF NOT EXISTS species_research_validation (
  id BIGSERIAL PRIMARY KEY,
  run_id UUID NOT NULL,
  taxon_id BIGINT NOT NULL,
  level TEXT NOT NULL CHECK (level IN ('error','warning','info')),
  message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### JSON Schema (validator)
- Validate presence/types for fields: `hosts`, `dependencies`, `soil_types`, `tolerances`.
- Enforce arrays of strings or objects with `{name, rank?, confidence?}`.
- Deduplicate normalized species names (case/whitespace/authorities stripped).

### Publish Step
- A server-side job merges validated fields into canonical `species` (existing schema) and logs a provenance record with the `run_id` and citations.

---

## 7) Prompt Templates (Deterministic JSON)

Use minimal, explicit templates. Example aspect prompt:
```text
Extract STRICT JSON for the aspect: HOSTS.
Use only the provided text. If unknown, return an empty list.

Schema:
{
  "species": "<scientific_name>",
  "hosts": [
    { "name": "<species or taxon>", "evidence": "<short quote>", "source_url": "<url>" }
  ],
  "sources": ["<url1>", "<url2>"]
}

Text:
<TRUNCATED_TEXT>
```

For general morphology/ecology blocks, produce normalized fields:
- height_m, diameter_cm, leaf_type, crown_shape
- drought_tolerance, flood_tolerance, shade_tolerance
- soil_types (enum from controlled vocabulary)

Always instruct the model to “Output only JSON, no prose.”

---

## 8) Ontology Integration

Leverage `ontology-generator` to produce RDF/OWL artifacts from staged/published data and publish to a triplestore.

- Map fields to OWL classes/properties via `ontology_config.json`.
- Generate OWL with OWLready2 and save.
- Optional: import to Blazegraph via the existing automation or expose via Jena/Fuseki.
- Pin exported RDF/OWL and derived CSVs to IPFS; store CIDs in Postgres for verifiability.

Automation options:
- Trigger ontology builds on publish events (webhook/queue).
- Version graphs (e.g., `http://example.org/treekipedia/v{semver}`) for traceability.

---

## 9) Admin Portal Enhancements

In `treekipedia/frontend/app/admin/page.tsx`:
- Replace hardcoded password with env-based config (e.g., Next.js runtime config) and/or wallet-gated admin.
- Tabs: `Server Stats`, `API Usage`, `Error Logs`, plus new:
  - `Queue`: current tasks, retry/abort controls, throughput.
  - `Batches`: create a batch (CSV or taxon_id range), start/pause, progress.
  - `LLM`: provider/model selection, health checks, latency benchmarks.
  - `Publish`: list completed runs awaiting review → publish to canonical + ontology.

Backend endpoints (Express):
- `GET /admin-api/queue` (pending/active/completed with run_ids)
- `POST /admin-api/batches` (start from species list/CSV)
- `POST /admin-api/queue/:runId/retry` | `.../abort`
- `GET /admin-api/llm/status` (model list, token/s)
- `POST /admin-api/publish/:runId` (publish staged → canonical + trigger ontology build)

---

## 10) Optional Python Microservice (Academic Ingestion)

Why: PDF parsing, scholarly search APIs, and complex scraping are easier in Python with existing libraries.

Responsibilities:
- Query Semantic Scholar/Publisher APIs; download open-access PDFs.
- Parse PDFs → text (`pdfminer.six`, `pypdf`) and metadata (DOI, journal, year).
- Run LM Studio prompts for structured extraction (OpenAI SDK with `base_url`).
- Push results to Postgres staging tables via SQLAlchemy/psycopg2.

Sample client (abbrev.):
```python
from openai import OpenAI
import requests, time, json

client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

def extract_aspect(text, aspect, model="phi-3-mini-4k-instruct-q4"):
    prompt = f"""
    Output STRICT JSON for aspect {aspect}. If unknown, use empty.
    Schema: {{"species":"","{aspect}":[],"sources":[]}}
    Text:\n{text[:2000]}
    """
    r = client.chat.completions.create(
        model=model,
        messages=[{"role":"user","content":prompt}],
        temperature=0.2,
        max_tokens=800,
    )
    return r.choices[0].message.content
```

---

## 11) Local Dev Runbook

Prereqs: Node 18+, Python 3.11+, Postgres 14+ with PostGIS, LM Studio (or Ollama).

1) Database
   - Create Postgres DB; apply PostGIS and existing Treekipedia schema.
   - Add staging tables (Section 6).

2) LLM
   - Start LM Studio server on `localhost:1234` and load the chosen model.

3) Backend (Treekipedia)
   - Set `.env` per Section 3.
   - `cd treekipedia/backend && yarn && yarn start` (or `node server.js`).

4) Frontend (Treekipedia)
   - `cd treekipedia/frontend && yarn && yarn dev`
   - Navigate to `/admin` for controls.

5) Optional Python Service
   - `cd ontology-generator && pip install -r requirements.txt`
   - Run import or custom ingestion scripts for PDFs/APIs.

6) Smoke Test
   - Choose a species in Admin → start research → verify queue, staging rows, and publish.

---

## 12) Observability & Reliability

- Centralized logging with request IDs and `run_id` correlation.
- Persist raw source blobs (truncated) for audit; cap size.
- Rate limiters per provider; circuit breaker on repeated failures.
- Idempotent publish step keyed by `run_id`.

---

## 13) Security, Ethics, and FAIR

- Respect terms, robots.txt; prioritize APIs; cite all sources.
- Store provenance (URL, timestamp, snippet) with each fact.
- FAIR: unique IDs, open formats (RDF/OWL), interoperable vocabularies (Darwin Core), reusable with licensing metadata.

---

## 14) Model Guidance for 18GB RAM

- Start with Phi-3 Mini (Q4) for consistency; fall back to Qwen2.5-1.5B for speed.
- Temperature ≤ 0.2; ensure JSON-only outputs; small context windows → aspect batching.
- Consider small fine-tunes (LoRA) later for ecology schema adherence.

---

## 15) Roadmap

Phase 0 — Bootstrap
- Wire provider abstraction; run LM Studio; single-species research end-to-end to staging.

Phase 1 — Admin & Staging
- Admin queue controls, batch creation, staging validation and publish flow.

Phase 2 — Ontology & IPFS
- Automate ontology export on publish; pin artifacts to IPFS; store CIDs.

Phase 3 — Academic Ingestion
- Python scholarly ingestion; PDF parsing; confidence scoring.

Phase 4 — Quality & Scale
- Deduplication across sources, NER-based validation, active learning prompts.

---

## 16) Appendix (DDL and Interfaces)

### Example DDL (staging)
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid
-- See Section 6 for table definitions
```

### Backend Provider Interface (TypeScript-ish)
```ts
type ChatMessage = { role: 'system' | 'user' | 'assistant'; content: string };
interface ChatClient {
  completion: (opts: { model: string; messages: ChatMessage[]; temperature?: number; max_tokens?: number }) => Promise<string>;
}
```

### Admin API (Express)
```http
GET /admin-api/queue
POST /admin-api/batches { species: string[] | { csvUrl } }
POST /admin-api/queue/:runId/retry
POST /admin-api/queue/:runId/abort
POST /admin-api/publish/:runId
GET  /admin-api/llm/status
```

---

This plan is tailored to the current repository: it reuses the existing research queue and controllers, extends provider support for local models, formalizes a staging/validation pipeline, integrates with the `ontology-generator`, and upgrades the admin portal to orchestrate local, verifiable deep research at scale.


