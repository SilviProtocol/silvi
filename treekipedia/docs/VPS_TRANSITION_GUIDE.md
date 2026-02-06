# Treekipedia VPS Transition Guide

This document provides a comprehensive analysis of the Digital Ocean VPS running the Treekipedia ecosystem, including current state, architecture, dependencies, and steps needed to transition from running code-server on the VM to running Claude Code locally with SSH access.

---

## Table of Contents
1. [VPS Overview](#vps-overview)
2. [Resource Analysis](#resource-analysis)
3. [Services Inventory](#services-inventory)
4. [Repository Architecture](#repository-architecture)
5. [Database Architecture](#database-architecture)
6. [Dependencies](#dependencies)
7. [Network Configuration](#network-configuration)
8. [Transition Steps](#transition-steps)
9. [Post-Transition Checklist](#post-transition-checklist)

---

## VPS Overview

| Property | Value |
|----------|-------|
| **Provider** | Digital Ocean |
| **Hostname** | tree-vm |
| **IP Address** | 167.172.143.162 |
| **OS** | Ubuntu 22.04 LTS |
| **Kernel** | 5.15.0-134-generic |
| **CPU** | 2 vCPU (DO-Premium-AMD) |
| **RAM** | 4 GB |
| **Disk** | 80 GB (67 GB used, 87% capacity) |
| **Swap** | 2 GB (1.1 GB used) |

### Current Resource Pressure
- **Memory**: 2.0 GB used + 1.1 GB swap = system is memory-constrained
- **Disk**: 87% full - needs cleanup before adding more services
- **CPU**: Low utilization (2 cores adequate for current workload)

---

## Resource Analysis

### Memory Consumers (Top Processes)

| Process | Memory | Notes |
|---------|--------|-------|
| Claude Code instances | ~600 MB | 2 instances running (324112, 1322327) |
| code-server | ~550 MB | Node processes for VS Code server |
| Apache Fuseki (Java) | ~260 MB | RDF/SPARQL triple store with 4GB heap |
| Gunicorn workers (4x) | ~340 MB | Biodiversity ontology Flask app |
| treekipedia-backend | ~60 MB | Main Express.js API server |
| location-predictor | ~28 MB | Python prediction service |
| RabbitMQ | ~35 MB | Message queue for async tasks |
| PM2 God Daemon | ~27 MB | Process manager |

**Total code-server + Claude Code footprint: ~1.1-1.2 GB**

### Disk Usage

| Path | Size | Contents |
|------|------|----------|
| `/var/www` | 11 GB | biodiversity-ontology app |
| `/var/lib/postgresql` | 9.2 GB | PostgreSQL data |
| `/opt` | 8.7 GB | Fuseki, other apps |
| `/root/silvi-open/treekipedia` | 9.1 GB | Treekipedia repo |
| `/root/.npm` | 2.0 GB | NPM cache |

### Treekipedia Repo Breakdown

| Directory | Size |
|-----------|------|
| `data/` | 5.1 GB (shapefiles, large datasets) |
| `database/` | 1.8 GB (backups, SQL files) |
| `frontend/` | 1.4 GB (node_modules, .next build) |
| `contracts/` | 353 MB (node_modules, artifacts) |
| `scripts/` | 110 MB |
| `backend/` | 37 MB |

---

## Services Inventory

### PM2-Managed Processes

| Name | Port | PID | Status | Purpose |
|------|------|-----|--------|---------|
| treekipedia-backend | 3000 | 360619 | online | Main Express API |
| location-predictor | 5002 | 3845277 | online | Python ML service |
| node (code-server) | 8080 | 2869183 | online | VS Code web IDE |

### Systemd Services (Enabled)

| Service | Port | Purpose |
|---------|------|---------|
| nginx | 80, 443 | Reverse proxy, SSL termination |
| postgresql@14-main | 5432 | Database |
| pm2-root | - | PM2 process manager autostart |
| fuseki | 3030 | Apache Jena SPARQL server |
| rabbitmq-server | 5672, 15672 | Message queue |
| docker | - | Container runtime |

### Docker Containers

| Container | Image | Purpose |
|-----------|-------|---------|
| pds | ghcr.io/bluesky-social/pds:0.4 | Bluesky PDS (AT Protocol) |
| watchtower | containrrr/watchtower:latest | Auto-update containers |

### Other Applications on VM

| Application | Location | Port | Stack |
|-------------|----------|------|-------|
| Biodiversity Ontology | `/var/www/biodiversity-ontology` | 8000 | Flask + Gunicorn |
| Bluesky PDS | Docker + `/pds` | 2583 | Node.js container |

---

## Repository Architecture

```
/root/silvi-open/treekipedia/
├── .env                    # Main environment config
├── CLAUDE.md               # Development guide
├── ACTIVE.md               # Production status
├── TODO.md                 # Task tracking
├── README.md               # Architecture overview
│
├── backend/                # Express.js API (Node 22)
│   ├── server.js          # Entry point (port 3000)
│   ├── controllers/       # Route handlers
│   ├── services/          # Business logic (grokResearch.js)
│   ├── routes/            # API route definitions
│   ├── middleware/        # Auth, rate limiting
│   └── package.json       # Dependencies
│
├── frontend/               # Next.js 15 + TypeScript
│   ├── app/               # App router pages
│   ├── components/        # React components
│   ├── lib/               # Types, utilities
│   └── .env.local         # Frontend env vars
│
├── contracts/              # Solidity (Hardhat)
│   ├── contracts/         # Smart contracts
│   └── test/              # Contract tests
│
├── database/               # SQL schemas
│   └── backups/           # Database dumps
│
├── scripts/                # Utility scripts
│   ├── db/                # Database migrations
│   ├── research/          # AI research scripts
│   └── tests/             # Test scripts
│
├── python-microservice/    # Python ML service
│   └── venv/              # Python virtual env
│
└── sparql/                 # SPARQL/RDF configs
```

### Git Configuration

- **Remote**: `https://github.com/SilviProtocol/silvi.git`
- **Current Branch**: `latest`
- **Main Branch**: `master`
- **Active Branches**: latest, master, djimotreekipedia, graphflow, feature-payment

---

## Database Architecture

### PostgreSQL Configuration

| Property | Value |
|----------|-------|
| Version | PostgreSQL 14.20 |
| Database | treekipedia |
| User | tree_user |
| Size | 8.8 GB |
| Extensions | postgis 3.2.0, vector 0.8.0 (pgvector), plpgsql |

### Key Tables

| Table | Rows | Size | Purpose |
|-------|------|------|---------|
| geohash_species_tiles | 6.46M | 4.6 GB | Geospatial occurrence tiles |
| species | 67,927 | 884 MB | Core species data (140+ fields) |
| intact_forest_landscapes_2021 | 6,819 | 1.2 GB | Forest polygons |
| ecoregions | 847 | 207 MB | WWF ecoregion boundaries |
| images | 31,796 | 22 MB | Species images with attribution |
| insights | varies | 1.4 MB | AI-generated atomic claims |
| research_queue | varies | 16 KB | Batch research queue |

### Species Table Schema (140+ fields)

Key field categories:
- **Taxonomy**: taxon_id, species_scientific_name, family, genus, class, taxonomic_order
- **Geography**: ecoregions, biomes, countries_native, countries_introduced, countries_invasive
- **Morphology**: growth_form, leaf_type, flower_color, fruit_type, bark_characteristics
- **Size**: maximum_height, maximum_diameter, lifespan, maximum_tree_age
- **Ecology**: habitat, ecological_function, tolerances, associated_species
- **Climate**: climate_type_koppengeiger, annual_temperature_range_c, annual_precipitation_mm
- **Conservation**: conservation_status, threats, national_conservation_status
- **Uses**: timber_value, non_timber_products, agroforestry_use_cases, cultural_significance
- **Stewardship**: stewardship_best_practices, disease_pest_management, pruning_maintenance
- **AI Research**: research_version, research_date, research_confidence, research_sources
- **Dual fields**: Most fields have `_ai` and `_human` variants

### Insights Table (Atomic Knowledge)

```sql
CREATE TABLE insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  taxon_id TEXT NOT NULL,
  claim_type TEXT NOT NULL,
  claim_value JSONB NOT NULL,
  confidence REAL DEFAULT 0.5,
  sources JSONB DEFAULT '[]',
  content_hash VARCHAR(64) UNIQUE,
  is_current BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Dependencies

### Backend (Node.js)

```json
{
  "axios": "^1.8.4",
  "cors": "^2.8.5",
  "csv-parser": "^3.2.0",
  "dotenv": "^16.4.7",
  "ethers": "^6.13.5",
  "express": "^4.21.2",
  "express-session": "^1.18.2",
  "multer": "^2.0.2",
  "node-cron": "^3.0.3",
  "pg": "^8.14.1",
  "uuid": "^11.1.0"
}
```

### Frontend (Next.js 15)

```json
{
  "next": "15.2.8",
  "react": "^18.3.1",
  "leaflet": "^1.9.4",
  "react-leaflet": "^5.0.0",
  "ethers": "^6.13.5",
  "wagmi": "^2.14.15",
  "@tanstack/react-query": "^5.69.0",
  "tailwindcss": "^3.4.1"
}
```

### System Dependencies

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | 22.21.0 | JavaScript runtime |
| npm | 10.9.4 | Package manager |
| Yarn | 1.22.22 | Package manager |
| Python | 3.10.12 | ML services, scripts |
| PostgreSQL | 14.20 | Database |
| PostGIS | 3.2.0 | Geospatial extension |
| pgvector | 0.8.0 | Vector similarity search |
| PM2 | 6.0.5 | Process manager |
| Nginx | latest | Reverse proxy |
| Docker | latest | Container runtime |
| certbot | installed | SSL certificate management |

---

## Network Configuration

### Nginx Virtual Hosts

| Domain | Port | Backend | SSL |
|--------|------|---------|-----|
| treekipedia-api.silvi.earth | 443 | localhost:3000 | Yes (Let's Encrypt) |
| codeserver.silvi.earth | 443 | localhost:8080 | Yes (Let's Encrypt) |
| treekipedia-graph-flow.silvi.earth | 443 | localhost:8000 | Yes (Let's Encrypt) |
| pds.silvi.earth | 443 | localhost:2583 | Yes (Let's Encrypt) |

### SSL Certificate Expiry

| Domain | Expires |
|--------|---------|
| codeserver.silvi.earth | Apr 19, 2026 |
| pds.silvi.earth | Apr 25, 2026 |
| treekipedia-api.silvi.earth | Apr 23, 2026 |
| treekipedia-graph-flow.silvi.earth | Mar 25, 2026 |

### Firewall (UFW) - Open Ports

| Port | Service |
|------|---------|
| 22 | SSH |
| 80, 443 | HTTP/HTTPS (Nginx) |
| 3000 | Treekipedia API (direct) |
| 3001 | Next.js dev server |
| 3030 | Fuseki SPARQL |
| 5432 | PostgreSQL |
| 5672, 15672 | RabbitMQ |
| 8080 | code-server |

### SSH Configuration

- Root login: **Enabled** (PermitRootLogin yes)
- Authorized keys: 4 keys in `/root/.ssh/authorized_keys`
- Password auth: Check `/etc/ssh/sshd_config` for current state

---

## Transition Steps

### Phase 1: Prepare Local Environment

1. **Install Claude Code locally**
   ```bash
   # On your local machine
   npm install -g @anthropic-ai/claude-code
   ```

2. **Ensure SSH key access**
   - Your SSH public key should already be in `/root/.ssh/authorized_keys`
   - Test connection: `ssh root@167.172.143.162`

3. **Configure SSH for convenience** (local `~/.ssh/config`)
   ```
   Host treekipedia
     HostName 167.172.143.162
     User root
     IdentityFile ~/.ssh/your_private_key
     ForwardAgent yes
   ```

### Phase 2: Stop code-server and Claude Code on VPS

1. **Stop PM2-managed code-server**
   ```bash
   ssh root@167.172.143.162
   pm2 stop node  # This is the code-server process
   pm2 delete node
   pm2 save
   ```

2. **Kill any running Claude Code processes**
   ```bash
   pkill -f "claude"
   ```

3. **Disable code-server nginx site** (optional, keeps SSL cert)
   ```bash
   rm /etc/nginx/sites-enabled/codeserver
   nginx -t && systemctl reload nginx
   ```

4. **Stop code-server systemd service** (if enabled)
   ```bash
   systemctl stop code-server@root
   systemctl disable code-server@root
   ```

### Phase 3: Free Up Resources

1. **Clear npm cache** (saves ~2GB)
   ```bash
   npm cache clean --force
   rm -rf /root/.npm/_cacache
   ```

2. **Remove unused Docker images**
   ```bash
   docker system prune -a
   ```

3. **Clean old log files**
   ```bash
   journalctl --vacuum-time=7d
   rm -rf /root/.pm2/logs/*.log
   ```

4. **Consider removing code-server package**
   ```bash
   # Only if you're sure you won't need it
   apt remove code-server
   ```

### Phase 4: Configure Local Claude Code for Remote

1. **Run Claude Code with SSH**
   ```bash
   # From your local machine
   claude --ssh treekipedia
   # Or with full path
   claude --ssh root@167.172.143.162
   ```

2. **Alternative: Use SSH tunnel + local Claude Code**
   ```bash
   # Terminal 1: SSH into VPS
   ssh treekipedia

   # Terminal 2: Run Claude Code locally, connecting to remote
   # This depends on Claude Code's remote features
   ```

### Phase 5: Verify Services Still Running

After transition, verify on VPS:

```bash
# Check PM2 processes
pm2 status

# Should show:
# - treekipedia-backend (online)
# - location-predictor (online)
# - node (code-server) should be REMOVED

# Check API is responding
curl https://treekipedia-api.silvi.earth/health

# Check database
sudo -u postgres psql -d treekipedia -c "SELECT COUNT(*) FROM species;"

# Check other services
systemctl status nginx postgresql fuseki rabbitmq-server
```

---

## Post-Transition Checklist

### Immediate Verification
- [ ] Can SSH into VPS from local machine
- [ ] Claude Code can connect via SSH
- [ ] treekipedia-backend is running (port 3000)
- [ ] API responds at https://treekipedia-api.silvi.earth
- [ ] PostgreSQL is accessible
- [ ] PM2 status shows correct processes

### Memory Verification
- [ ] Check `free -h` - should show ~1GB more available
- [ ] Swap usage should decrease

### Security
- [ ] Review `/root/.ssh/authorized_keys` - remove old keys
- [ ] Consider disabling root SSH login (create admin user first)
- [ ] Review UFW rules - close port 8080 if code-server removed

### Cleanup (Optional)
- [ ] Remove `/etc/nginx/sites-available/codeserver` config
- [ ] Remove code-server SSL cert (or keep for other use)
- [ ] Archive old PM2 logs

### Documentation Updates
- [ ] Update team on new access method
- [ ] Document local Claude Code SSH command
- [ ] Update any CI/CD that referenced code-server

---

## Expected Resource Savings

| Resource | Before | After | Savings |
|----------|--------|-------|---------|
| RAM | ~2.0 GB used | ~0.9 GB used | ~1.1 GB |
| Swap | ~1.1 GB used | ~0.5 GB used | ~0.6 GB |
| CPU | 2 Claude processes | 0 | Reduced load |
| Disk (npm cache) | 2 GB | ~100 MB | ~1.9 GB |

---

## Environment Variables Reference

The VPS has these env file locations:
- **Root config**: `/root/silvi-open/treekipedia/.env` (DATABASE_URL, API keys)
- **Frontend**: `/root/silvi-open/treekipedia/frontend/.env.local` (NEXT_PUBLIC_* vars)
- **Biodiversity Ontology**: `/var/www/biodiversity-ontology/.env`

**Critical secrets in .env** (do not commit):
- DATABASE_URL
- API keys (Perplexity, OpenAI, XAI, Anthropic, Lighthouse, Infura)
- PRIVATE_KEY (blockchain wallet)
- SESSION_SECRET

---

## Contact & Support

- **Repository**: https://github.com/SilviProtocol/silvi
- **VPS IP**: 167.172.143.162
- **Primary Domains**:
  - treekipedia-api.silvi.earth
  - treekipedia-graph-flow.silvi.earth
  - pds.silvi.earth

---

*Document generated: 2026-02-04*
*Current branch: latest*
