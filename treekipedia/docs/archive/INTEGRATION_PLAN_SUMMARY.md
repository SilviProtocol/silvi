# 🎯 GraphFlow → Treekipedia Integration Plan

## Executive Summary

**Goal**: Rebuild GraphFlow admin portal as integrated Next.js pages in Treekipedia while keeping Python backend as a headless microservice.

**Timeline**: 6 weeks solo / 3 weeks with team
**Complexity**: Medium-High (3,700 lines of Python must stay, 4,500 lines to refactor)
**Risk**: Low (with proper testing and rollback plan)

---

## What the Research Agent Found

### Current GraphFlow Architecture

**Flask Application** (4,501 lines of Python):
- 7 HTML template pages
- 58 API endpoints
- 3 main workflows:
  1. CSV file upload → OWL ontology generation
  2. Google Sheets import → OWL generation
  3. PostgreSQL → Fuseki sync (67k species)

**Critical Dependencies** (MUST stay Python):
- `owlready2` (1,200 lines) - OWL ontology manipulation (no JS alternative)
- `rdflib` (800 lines) - RDF triple generation
- `gspread` (600 lines) - Google Sheets API
- `postgres_to_fuseki_sync.py` (900 lines) - Complex batch processing

**Total Lines That CANNOT Be Ported to Node.js**: ~3,700 lines

---

## Proposed New Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TREEKIPEDIA                              │
│            (What users see and interact with)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  NEXT.JS FRONTEND (Vercel / localhost:3000)                │
│  ├── /admin                  (Dashboard)                   │
│  ├── /admin/sync             (PostgreSQL → Fuseki)         │
│  ├── /admin/upload           (CSV ontology generation)     │
│  ├── /admin/sheets           (Google Sheets import)        │
│  ├── /admin/monitor          (System status)               │
│  └── /admin/sparql           (SPARQL query editor)         │
│                                                             │
│       ↓ API calls to backend                               │
│                                                             │
│  EXPRESS BACKEND (Digital Ocean :5001)                     │
│  ├── POST /api/admin/sync-species                          │
│  ├── POST /api/admin/upload-ontology                       │
│  ├── GET  /api/admin/status                                │
│  └── All other admin endpoints...                          │
│                                                             │
│       ↓ Proxies to Python microservice                     │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              PYTHON MICROSERVICE                            │
│        (Hidden backend service - users never see)           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Flask API-only (localhost:5002 - NOT public)              │
│  ├── POST /api/sync/species        (Stream progress)       │
│  ├── POST /api/ontology/generate   (OWL creation)          │
│  ├── POST /api/sheets/import       (Google Sheets)         │
│  ├── GET  /api/status/fuseki       (Check connection)      │
│  └── All Python-only operations...                         │
│                                                             │
│  Core Functionality:                                        │
│  ├── owlready2 - OWL manipulation                          │
│  ├── rdflib - RDF generation                               │
│  ├── postgres_to_fuseki_sync - Batch processing            │
│  ├── multi_sheet_biodiversity_generator - Field detection  │
│  └── Google Sheets API integration                         │
│                                                             │
│  Accessed by: Express backend ONLY (localhost)             │
│  Not exposed to: Internet / external traffic               │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Python Microservice Extraction (Week 1-2)

**Goal**: Convert GraphFlow to headless API-only service

**Tasks**:
1. ✅ Create `api_only.py` (strip all HTML templates)
2. ✅ Design REST API endpoints (58 total)
3. ✅ Add CORS (allow only localhost:5001)
4. ✅ Implement SSE for progress streaming
5. ✅ Add health check endpoints
6. ✅ Write API documentation (OpenAPI spec)

**Deliverables**:
- `graphflow-microservice/api_only.py`
- `API_SPEC.yaml` (OpenAPI documentation)
- Unit tests for each endpoint

**Time Estimate**: 40 hours

---

### Phase 2: Express Backend Integration (Week 2-3)

**Goal**: Add proxy routes from Express to Python service

**Tasks**:
1. ✅ Create `/api/admin/*` routes in Express
2. ✅ Implement file upload proxy (multipart/form-data)
3. ✅ Add SSE proxy for progress streaming
4. ✅ Create authentication middleware (admin-only)
5. ✅ Add error handling and logging
6. ✅ Write integration tests

**Deliverables**:
- `treekipedia/backend/controllers/admin.js`
- `treekipedia/backend/middleware/requireAdmin.js`
- Integration tests

**Time Estimate**: 30 hours

---

### Phase 3: Next.js Admin UI (Week 3-5)

**Goal**: Rebuild all 7 GraphFlow pages in Next.js

**Pages to Create**:

1. **`/admin`** - Dashboard
   - System status cards
   - Quick action buttons
   - Recent activity log

2. **`/admin/sync`** - PostgreSQL → Fuseki Sync
   - Database table list
   - Sync progress bar
   - Triple count display
   - Batch size configuration

3. **`/admin/upload`** - CSV Ontology Generation
   - File upload dropzone
   - Field detection preview
   - Ontology quality score
   - Download generated OWL

4. **`/admin/sheets`** - Google Sheets Import
   - Sheets ID input
   - Sheet preview
   - Field mapping UI
   - Import progress

5. **`/admin/monitor`** - System Monitor
   - Fuseki stats (triples, graphs)
   - PostgreSQL stats (tables, rows)
   - Server health metrics
   - Recent sync history

6. **`/admin/sparql`** - SPARQL Query Editor
   - CodeMirror editor
   - Query results table
   - Sample queries dropdown
   - Export results (JSON/CSV)

7. **`/admin/versions`** - Version Management
   - Ontology version history
   - Create snapshot
   - Rollback functionality

**Shared Components**:
- `StatusCard` - System status indicator
- `ProgressBar` - Sync/upload progress
- `DataTable` - Generic table with sorting
- `CodeEditor` - SPARQL query editor
- `FileDropzone` - File upload area

**Time Estimate**: 80 hours

---

### Phase 4: Testing & QA (Week 5-6)

**Test Types**:

1. **Unit Tests** (Python)
   - Test each Python API endpoint
   - Mock PostgreSQL/Fuseki calls
   - Coverage target: >80%

2. **Integration Tests** (Express)
   - Test Express → Python proxy
   - Test file uploads
   - Test SSE streaming
   - Coverage target: >70%

3. **E2E Tests** (Playwright)
   - Test complete sync workflow
   - Test CSV upload flow
   - Test Google Sheets import
   - Test SPARQL queries

4. **Load Tests** (k6)
   - Test sync with 67k species
   - Test concurrent uploads
   - Test Fuseki query performance

**Time Estimate**: 40 hours

---

### Phase 5: Deployment (Week 6)

**Deployment Steps**:

1. **Deploy Python Microservice**
   ```bash
   # On Digital Ocean
   cd /opt/treekipedia-python-service
   systemctl start treekipedia-python
   ```

2. **Update Express Backend**
   ```bash
   # Deploy new admin routes
   pm2 restart treekipedia-backend
   ```

3. **Deploy Next.js Frontend**
   ```bash
   # Deploy to Vercel
   vercel deploy --prod
   ```

4. **Dual-Run Period** (2 weeks)
   - Keep old GraphFlow accessible at /legacy-admin
   - Monitor for issues
   - Compare performance

5. **Full Cutover**
   - Disable old GraphFlow
   - Update documentation
   - Announce to users

**Time Estimate**: 24 hours

---

## Total Time Estimate

| Phase | Solo Developer | With Team (2 devs) |
|-------|----------------|---------------------|
| Phase 1: Python API | 40 hours | 24 hours |
| Phase 2: Express | 30 hours | 18 hours |
| Phase 3: Next.js UI | 80 hours | 48 hours |
| Phase 4: Testing | 40 hours | 24 hours |
| Phase 5: Deployment | 24 hours | 12 hours |
| **Total** | **214 hours** | **126 hours** |
| **Calendar Time** | **6 weeks** | **3 weeks** |

---

## Risk Assessment & Mitigation

### High Risks

**Risk 1: Python service crashes during sync**
- **Mitigation**: Add auto-restart (systemd), comprehensive error handling
- **Rollback**: Keep old GraphFlow running for 1 month backup

**Risk 2: SSE streaming breaks on slow networks**
- **Mitigation**: Add WebSocket fallback, implement heartbeat pings
- **Test**: Simulate slow network with throttling

**Risk 3: File uploads >100MB fail**
- **Mitigation**: Chunk uploads, add progress resumption
- **Test**: Load test with large CSV files

### Medium Risks

**Risk 4: Authentication bypass**
- **Mitigation**: Middleware on all `/admin/*` routes, rate limiting
- **Test**: Penetration testing

**Risk 5: Fuseki connection timeout during large syncs**
- **Mitigation**: Increase timeout, batch size tuning, retry logic
- **Test**: Load test with 67k species

### Low Risks

**Risk 6: UI inconsistency with Treekipedia design**
- **Mitigation**: Use existing Tailwind classes, design review
- **Test**: Visual regression testing

---

## Rollback Plan

**If integration fails, rollback in <10 minutes:**

1. **Keep old GraphFlow running** (systemd service)
   ```bash
   systemctl start graphflow-legacy
   ```

2. **Nginx config** (switch back)
   ```nginx
   # Revert /admin to GraphFlow
   location /admin {
     proxy_pass http://localhost:5002;
   }
   ```

3. **DNS failover** (if needed)
   - Point admin.treekipedia.silvi.earth to old server

**Backup retention**: 1 month

---

## Testing Strategy

### 1. Unit Tests (Python)

```python
# test_api.py
def test_sync_species_endpoint():
    response = client.post('/api/sync/species', json={'batchSize': 1000})
    assert response.status_code == 200
    assert 'stream' in response.headers['content-type']

def test_fuseki_status():
    response = client.get('/api/status/fuseki')
    data = response.json()
    assert 'status' in data
    assert data['triples'] > 0
```

### 2. Integration Tests (Express)

```javascript
// test/admin.test.js
describe('Admin API Proxy', () => {
  it('should proxy sync request to Python service', async () => {
    const response = await request(app)
      .post('/api/admin/sync-species')
      .send({ batchSize: 100 })
      .expect(200);

    expect(response.headers['content-type']).toContain('event-stream');
  });
});
```

### 3. E2E Tests (Playwright)

```typescript
// e2e/sync.spec.ts
test('complete sync workflow', async ({ page }) => {
  await page.goto('http://localhost:3000/admin/sync');
  await page.click('text=Start Sync');

  // Wait for progress
  await page.waitForSelector('.progress-bar');

  // Verify completion
  await page.waitForSelector('text=Sync Complete', { timeout: 600000 });
});
```

### 4. Load Tests (k6)

```javascript
// load-test.js
export default function () {
  http.post('http://localhost:5001/api/admin/sync-species', {
    batchSize: 1000
  });
}

// Run: k6 run --vus 10 --duration 5m load-test.js
```

---

## Success Criteria

✅ **All 58 endpoints working** (100% feature parity)
✅ **Sync 67k species in <30 min** (same or better performance)
✅ **Zero downtime deployment** (dual-run period)
✅ **Admin auth working** (only admins access /admin)
✅ **UI matches Treekipedia** (emerald theme, responsive)
✅ **Tests passing** (>80% Python, >70% Express, E2E green)
✅ **No regressions** (existing Treekipedia features intact)
✅ **Documentation complete** (API docs, user guide, deployment guide)

---

## Next Steps (Right Now)

### Step 1: Review & Approve (30 min)

**Questions to answer**:
- ✅ Approve architecture?
- ✅ Approve timeline (6 weeks)?
- ✅ Approve Python microservice on port 5002?
- ✅ Admin authentication strategy? (wallet-based? JWT?)

### Step 2: Set Up Development Environment (1 hour)

```bash
# 1. Create Python microservice directory
mkdir -p treekipedia/python-microservice

# 2. Copy GraphFlow code
cp -r graphflow-extracted/silvi-open-graphflow/* treekipedia/python-microservice/

# 3. Create api_only.py
cd treekipedia/python-microservice
# (I'll create this file)

# 4. Test local setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 api_only.py
```

### Step 3: Start Phase 1 Implementation (Week 1)

I can start building **right now** if you approve!

**Want me to**:
1. ✅ Create `api_only.py` (headless Python API)?
2. ✅ Create OpenAPI spec for all endpoints?
3. ✅ Create first Next.js admin page (/admin dashboard)?
4. ✅ All of the above?

---

## Files I'll Create

When you say "go", I'll create:

1. **Python Microservice**:
   - `treekipedia/python-microservice/api_only.py`
   - `treekipedia/python-microservice/API_SPEC.yaml`
   - `treekipedia/python-microservice/.env.example`
   - `treekipedia/python-microservice/README.md`

2. **Express Backend**:
   - `treekipedia/backend/controllers/admin.js`
   - `treekipedia/backend/middleware/requireAdmin.js`
   - `treekipedia/backend/services/pythonService.js`

3. **Next.js Frontend**:
   - `treekipedia/frontend/app/admin/page.tsx`
   - `treekipedia/frontend/app/admin/sync/page.tsx`
   - `treekipedia/frontend/components/admin/StatusCard.tsx`
   - `treekipedia/frontend/components/admin/ProgressBar.tsx`
   - And 10+ more components...

4. **Tests**:
   - `treekipedia/python-microservice/tests/test_api.py`
   - `treekipedia/backend/tests/admin.test.js`
   - `treekipedia/frontend/e2e/admin.spec.ts`

5. **Documentation**:
   - `ADMIN_PORTAL_GUIDE.md` (user documentation)
   - `DEPLOYMENT_GUIDE.md` (production deployment)
   - `TESTING_GUIDE.md` (how to run tests)

---

## Ready to Start? 🚀

Say **"GO"** and I'll start Phase 1 implementation immediately!

Or if you have questions/concerns about the plan, let me know and I'll adjust.
