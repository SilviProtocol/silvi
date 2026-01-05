# Treekipedia Local Deployment Guide

This guide will help you deploy Treekipedia locally on your machine.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js** (v18 or higher) - [Download](https://nodejs.org/)
- **PostgreSQL** (v14 or higher) - [Download](https://www.postgresql.org/download/)
- **npm** or **yarn** package manager
- **Git** (for version control)

## Quick Start

### 1. Database Setup

#### Install PostgreSQL with PostGIS

**macOS (using Homebrew):**
```bash
brew install postgresql@14 postgis
brew services start postgresql@14
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql-14 postgresql-14-postgis-3
sudo systemctl start postgresql
```

#### Create Database

```bash
# Access PostgreSQL
psql postgres

# Create database and user
CREATE DATABASE treekipedia;
CREATE USER treekipedia_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE treekipedia TO treekipedia_user;

# Exit psql
\q
```

#### Initialize Database Schema

```bash
# Navigate to database directory
cd treekipedia/database

# Connect to the database and run schema setup
psql -U treekipedia_user -d treekipedia -f current-schema.sql

# Enable PostGIS extension
psql -U treekipedia_user -d treekipedia -f 01_enable_postgis.sql

# (Optional) Set up geospatial tables
psql -U treekipedia_user -d treekipedia -f 02_create_geohash_tiles_table.sql
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd treekipedia/backend

# Install dependencies
npm install

# Create environment file
cp .env.example ../.env

# Edit the .env file with your configuration
nano ../.env
```

**Minimal `.env` configuration for local development:**

```env
# Database
DATABASE_URL=postgresql://treekipedia_user:your_secure_password@localhost:5432/treekipedia

# Server
PORT=5000
NODE_ENV=development

# CORS (allow all origins for local dev)
DEBUG_CORS=true

# Blockchain (optional for basic testing)
BASE_RPC_URL=https://base-sepolia.infura.io/v3/YOUR_INFURA_KEY
INFURA_API_KEY=your_infura_key

# AI APIs (optional - needed for research features)
OPENAI_API_KEY=your_openai_key
PERPLEXITY_API_KEY=your_perplexity_key
```

**Start the backend server:**

```bash
# Development mode with auto-reload
npm install -g nodemon
nodemon server.js

# Or standard mode
node server.js
```

The backend should now be running at `http://localhost:5000`

**Test the backend:**
```bash
curl http://localhost:5000/api
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory
cd treekipedia/frontend

# Install dependencies
npm install

# Create environment file
cp .env.example .env.local

# Edit the .env.local file
nano .env.local
```

**Minimal `.env.local` configuration:**

```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:5000

# Blockchain (optional for basic testing)
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your_project_id

# Contract addresses (use placeholder for local dev)
NEXT_PUBLIC_PAYMENT_CONTRACT_ADDRESS=0x0000000000000000000000000000000000000000
NEXT_PUBLIC_NFT_CONTRACT_ADDRESS=0x0000000000000000000000000000000000000000
```

**Start the frontend:**

```bash
npm run dev
```

The frontend should now be running at `http://localhost:3000`

### 4. Access the Application

Open your browser and navigate to:
- **Frontend:** `http://localhost:3000`
- **Backend API:** `http://localhost:5000/api`

## Database Population (Optional)

### Add Sample Species Data

If you want to populate the database with initial species data:

```bash
# Check if you have any CSV files or import scripts in the database directory
cd treekipedia/database

# If you have seed data, you can import it
# Example: Import species data
psql -U treekipedia_user -d treekipedia -c "COPY species FROM '/path/to/species.csv' CSV HEADER;"
```

### Load Species Images

If you have the images JSON file:

```bash
cd treekipedia/database

# Insert images from JSON
psql -U treekipedia_user -d treekipedia

# Then run SQL commands to insert from treekipedia_images_full.json
# (You may need a custom import script for JSON data)
```

## Development Workflow

### Running Both Frontend and Backend

**Terminal 1 - Backend:**
```bash
cd treekipedia/backend
nodemon server.js
```

**Terminal 2 - Frontend:**
```bash
cd treekipedia/frontend
npm run dev
```

### Common Development Tasks

**Check database connection:**
```bash
psql -U treekipedia_user -d treekipedia -c "SELECT COUNT(*) FROM species;"
```

**View backend logs:**
```bash
# Logs are output to console when running with nodemon or node
tail -f server_log.txt
```

**Clear Next.js cache:**
```bash
cd treekipedia/frontend
rm -rf .next
npm run dev
```

## Troubleshooting

### PostgreSQL Connection Issues

**Error: "role does not exist" or "password authentication failed"**

Check your PostgreSQL configuration:
```bash
# Edit pg_hba.conf to allow local connections
sudo nano /etc/postgresql/14/main/pg_hba.conf

# Change peer to md5 for local connections:
# local   all             all                                     md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Port Already in Use

**Backend (Port 5000):**
```bash
# Find and kill process using port 5000
lsof -ti:5000 | xargs kill -9
```

**Frontend (Port 3000):**
```bash
# Find and kill process using port 3000
lsof -ti:3000 | xargs kill -9
```

### Frontend Not Connecting to Backend

1. Check that backend is running: `curl http://localhost:5000/api`
2. Verify `NEXT_PUBLIC_API_URL` in `.env.local` is set to `http://localhost:5000`
3. Check browser console for CORS errors
4. Ensure `DEBUG_CORS=true` in backend `.env` file

### Database Schema Issues

If you encounter schema errors, you may need to drop and recreate:

```bash
psql -U treekipedia_user -d postgres

DROP DATABASE treekipedia;
CREATE DATABASE treekipedia;
GRANT ALL PRIVILEGES ON DATABASE treekipedia TO treekipedia_user;

\c treekipedia
\i treekipedia/database/current-schema.sql
\i treekipedia/database/01_enable_postgis.sql
```

## Feature Configuration

### Enabling AI Research (Optional)

To enable AI-powered species research:

1. Get API keys:
   - OpenAI: https://platform.openai.com/api-keys
   - Perplexity: https://www.perplexity.ai/settings/api

2. Add to backend `.env`:
```env
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...
```

3. Restart backend server

### Enabling Blockchain Features (Optional)

To enable payment and NFT minting:

1. Get Infura API key: https://infura.io/

2. Deploy contracts or use existing addresses

3. Update both `.env` files with contract addresses and RPC endpoints

4. Get WalletConnect project ID: https://cloud.walletconnect.com/

## Testing the Application

### Test Species Search

1. Navigate to `http://localhost:3000`
2. Use the search bar to search for species
3. Click on a species to view details

### Test API Endpoints

```bash
# Search species
curl "http://localhost:5000/species?q=oak"

# Get species details (use a valid taxon_id from your database)
curl "http://localhost:5000/species/123456"

# Get treederboard
curl "http://localhost:5000/treederboard"
```

## Production Deployment Differences

For production deployment, you'll need to:

1. Set `NODE_ENV=production`
2. Use secure PostgreSQL credentials
3. Configure proper CORS origins (remove `DEBUG_CORS=true`)
4. Set up SSL/TLS certificates
5. Use production blockchain networks (not Sepolia testnet)
6. Configure proper logging and monitoring
7. Set up process manager (PM2) for backend
8. Build frontend for production: `npm run build && npm start`

## Next Steps

- Explore the [API Documentation](treekipedia/API.md)
- Review the [Frontend Style Guide](treekipedia/frontend/STYLE_GUIDE.md)
- Check out the [Database Schema Documentation](treekipedia/database/README.md)

## Getting Help

If you encounter issues:

1. Check the logs in both frontend and backend terminals
2. Review the database connection settings
3. Ensure all environment variables are correctly set
4. Check that all required services are running

For more information, see the main [README.md](README.md)
