# GraphFlow Integration - Quick Reference

**Full Plan:** See [GRAPHFLOW_INTEGRATION_PLAN.md](./GRAPHFLOW_INTEGRATION_PLAN.md)

---

## At a Glance

### Current State
- **Flask app** at 4,501 lines of Python
- **58 API endpoints** across 7 HTML templates
- **Critical dependencies**: owlready2, rdflib, gspread (MUST stay Python)

### Target State
- **Next.js admin portal** in `/app/admin/`
- **Python microservice** on port 5002 (headless)
- **Express proxy layer** in `/backend/controllers/admin/`

---

## Architecture Decision

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│              │         │              │         │              │
│   Next.js    │────────▶│   Express    │────────▶│   Python     │
│   Frontend   │         │   Proxy      │         │   Service    │
│              │         │              │         │              │
└──────────────┘         └──────────────┘         └──────────────┘
     (UI/UX)              (Auth, Files,          (OWL, RDF,
                           Sessions)               gspread)
```

**Why This Split?**
- ✅ owlready2/rdflib have no JavaScript equivalent
- ✅ Next.js provides modern, responsive UI
- ✅ Express handles auth, file uploads, sessions
- ✅ Python service is stateless, scalable
- ✅ Easy rollback to Flask if needed

---

## Quick Stats

| Metric | Value |
|--------|-------|
| **Total Endpoints** | 58 |
| **Python-Only Code** | ~3,700 lines (OWL/RDF processing) |
| **Portable Code** | ~800 lines (metadata, validation) |
| **Templates to Migrate** | 7 HTML files |
| **Estimated Timeline** | 6 weeks solo, 3 weeks with team |
| **Total Dev Hours** | 234 hours |

---

## File Locations (After Integration)

### Python Microservice
```
graphflow-service/          # NEW - Standalone Python app
├── app.py                  # Flask API (no templates)
├── api/
│   ├── ontology.py         # Ontology generation
│   ├── postgres.py         # RDF conversion
│   └── sheets.py           # Google Sheets
├── services/
│   ├── owl_generator.py    # MultiSheetBiodiversityGenerator
│   ├── rdf_converter.py    # PostgreSQLFusekiSync
│   └── sheets_client.py    # SheetsIntegration
└── Dockerfile
```

### Express Backend
```
treekipedia/backend/
├── controllers/admin/      # NEW
│   ├── ontology.js
│   ├── postgresSync.js
│   └── sheets.js
├── middleware/
│   ├── pythonProxy.js      # NEW - Proxy to Python
│   └── streamProgress.js   # NEW - SSE handler
└── routes/
    └── admin.js            # NEW - Admin routes
```

### Next.js Frontend
```
treekipedia/frontend/
└── app/admin/              # NEW
    ├── page.tsx            # Dashboard
    ├── ontology/
    │   ├── upload/
    │   ├── sheets/
    │   └── sessions/
    ├── postgres-sync/
    ├── fuseki/
    └── components/
```

---

## Critical Endpoints (Python-Only)

These **CANNOT** be ported to Node.js:

| Endpoint | Why Python-Only |
|----------|-----------------|
| `POST /api/v1/ontology/generate` | owlready2 - OWL creation |
| `POST /api/v1/postgres/convert-table` | rdflib - RDF serialization |
| `POST /api/v1/sheets/import` | gspread - Google Sheets API |
| `POST /api/v1/analyze/fields` | Pattern matching + OWL |

---

## Implementation Phases

### Phase 1: Python Microservice (Week 1-2)
- [ ] Extract Python into standalone service
- [ ] Remove HTML template dependencies
- [ ] Add OpenAPI documentation
- [ ] Create Docker container
- [ ] Port: 5002

**Deliverable:** Headless Python API

### Phase 2: Express Integration (Week 2-3)
- [ ] Create `/backend/controllers/admin/`
- [ ] Implement Python proxy middleware
- [ ] Add SSE stream handlers
- [ ] File upload endpoints

**Deliverable:** Proxy layer working

### Phase 3: Next.js Components (Week 3-5)
- [ ] Create `/app/admin/` structure
- [ ] Build 5 main pages
- [ ] Implement 15+ reusable components
- [ ] Real-time progress updates

**Deliverable:** Full admin portal

### Phase 4: Testing (Week 5-6)
- [ ] E2E tests (Playwright)
- [ ] Integration tests
- [ ] Load testing
- [ ] Performance optimization

**Deliverable:** Production-ready code

### Phase 5: Deployment (Week 6-7)
- [ ] Docker deployment
- [ ] Monitoring setup
- [ ] Documentation
- [ ] Go live

**Deliverable:** Running in production

---

## Key Technologies

### Must Stay Python
- **owlready2** - OWL ontology manipulation
- **rdflib** - RDF graph creation/serialization
- **gspread** - Google Sheets API
- **psycopg2** - PostgreSQL (for RDF conversion)

### New Stack
- **Next.js 15** - Frontend framework
- **Express.js** - API proxy/routing
- **React Query** - Server state management
- **Axios** - HTTP client
- **Playwright** - E2E testing

---

## API Examples

### Python Service Call (from Express)

```javascript
// Express controller
const pythonClient = axios.create({
  baseURL: 'http://localhost:5002/api/v1'
});

const result = await pythonClient.post('/ontology/generate', {
  session_id: 'uuid',
  files: ['mvp.csv', 'options.csv'],
  ontology_name: 'treekipedia-ontology'
});
```

### Frontend Call (from Next.js)

```typescript
// Next.js component
const { data, isLoading } = useMutation({
  mutationFn: async (files: File[]) => {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));

    const response = await fetch('/api/admin/ontology/upload', {
      method: 'POST',
      body: formData
    });

    return response.json();
  }
});
```

---

## Testing Strategy

### Python Service Tests
```bash
cd graphflow-service
pytest tests/ -v
```

### Express Integration Tests
```bash
cd treekipedia/backend
npm run test:integration
```

### E2E Tests
```bash
cd treekipedia/frontend
npx playwright test
```

### Load Testing
```bash
k6 run tests/load/ontology-generation.js
```

---

## Rollback Plan

**If something goes wrong:**

1. **Immediate** (< 5 minutes):
   - Revert nginx config to Flask app
   - Restart old Flask service
   - Disable Next.js admin routes

2. **Dual-Run Period** (2 weeks):
   - Keep Flask running on port 5003
   - Run Next.js admin in parallel
   - Compare outputs for validation

3. **Emergency Command**:
   ```bash
   # Rollback script
   ./scripts/rollback-to-flask.sh
   ```

---

## Success Criteria

- [ ] All 58 endpoints functional
- [ ] < 5s response time for ontology generation
- [ ] < 30s for PostgreSQL batch (1000 records)
- [ ] Real-time progress updates working
- [ ] Mobile responsive
- [ ] Zero data loss
- [ ] 99.9% uptime

---

## Performance Targets

| Operation | Target | Current |
|-----------|--------|---------|
| Ontology generation (100 fields) | < 5 sec | ~3 sec |
| PostgreSQL batch (1000 records) | < 30 sec | ~25 sec |
| File upload (10MB) | < 2 sec | ~1 sec |
| API proxy latency | < 100ms | TBD |
| SSE connection setup | < 500ms | TBD |

---

## Monitoring

### Health Checks
```bash
# Python service
curl http://localhost:5002/api/v1/health

# Express proxy
curl http://localhost:5001/api/admin/health

# Full system
curl http://localhost:3000/api/admin/health
```

### Logs
```bash
# Python service
tail -f graphflow-service/logs/app.log

# Express backend
tail -f treekipedia/backend/logs/admin.log

# Combined view
docker-compose logs -f graphflow python-service
```

---

## Common Commands

### Development
```bash
# Start Python service
cd graphflow-service && python app.py

# Start Express backend
cd treekipedia/backend && npm run dev

# Start Next.js frontend
cd treekipedia/frontend && npm run dev
```

### Testing
```bash
# Run all tests
npm run test:all

# Run specific test suite
npm run test:admin
npm run test:e2e
npm run test:integration
```

### Deployment
```bash
# Build Docker images
docker-compose build

# Deploy all services
docker-compose up -d

# Check status
docker-compose ps
```

---

## Contact Points

**Python Service Issues:**
- File: `graphflow-service/app.py`
- Port: 5002
- Logs: `graphflow-service/logs/app.log`

**Express Proxy Issues:**
- File: `treekipedia/backend/controllers/admin/`
- Port: 5001
- Logs: `treekipedia/backend/logs/admin.log`

**Frontend Issues:**
- File: `treekipedia/frontend/app/admin/`
- Port: 3000
- Browser console

---

## Next Steps

1. **Review** this plan with team
2. **Set up** Python service development environment
3. **Create** project timeline in GitHub/Jira
4. **Begin** Phase 1 implementation

---

**Last Updated:** October 19, 2025
**Document:** Quick Reference for [GRAPHFLOW_INTEGRATION_PLAN.md](./GRAPHFLOW_INTEGRATION_PLAN.md)
