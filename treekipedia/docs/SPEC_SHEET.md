Treekipedia Technical Specification
1. Overview
Treekipedia is an open-source, multi-chain platform designed to catalog comprehensive tree species data and incentivize user contributions through blockchain-based Contreebution NFTs. The platform deploys on Base, Celo, Optimism, and Arbitrum—all EVM-compatible Layer 2 networks—using PostgreSQL for centralized data storage, Express.js for the backend, and Next.js for the frontend. It integrates the Ethereum Attestation Service (EAS) for on-chain attestations and IPFS for decentralized storage of research data, NFT metadata, and public data exports. Treekipedia emphasizes openness and collaboration, making its species data publicly accessible through periodic exports to IPFS via Lighthouse, aligning with potential funding opportunities from Filecoin.

2. Objectives
Provide a searchable database of tree species with auto-complete functionality.
Display detailed species pages, distinguishing between researched and unresearched species.
Enable users to fund AI-driven research for unresearched species by minting Contreebution NFTs on their chosen chain.
Support multi-chain deployment on Base, Celo, Optimism, and Arbitrum for user flexibility.
Maintain a Treederboard to showcase top contributors, with optional display names linked to wallet addresses.
Make the species data publicly accessible through regular exports to IPFS, fostering an open-source and collaborative environment.

3. Architecture
Treekipedia’s architecture is designed to support a seamless, multi-chain, AI-driven platform for tree species data management, research incentivization, and decentralized data storage. The system leverages:
A centralized backend for data processing and API management.
A decentralized blockchain layer for NFTs and attestations.
IPFS for permanent, open-access data storage.
Below is a detailed breakdown of each component and how they interact.

3.1 System Components
Frontend: Next.js (React, TypeScript)


Provides a user-friendly interface for species search, auto-complete, species details, and Treederboard rankings.
Integrates wallet connections (e.g., MetaMask) for user actions like funding research.
Backend: Express.js (Node.js)


Manages API endpoints for species data, user profiles, and research funding.
Orchestrates the AI Research Process, database updates, IPFS uploads, and blockchain interactions.
Database: PostgreSQL (version 14.17)


Stores species data, user profiles, and Contreebution NFT records.
Includes triggers and functions to update user points automatically upon NFT minting.
Blockchain


Ethereum Attestation Service (EAS): Used for on-chain attestations of research data.
Contreebution NFTs (ERC-721): Deployed on Base, Celo, Optimism, and Arbitrum (all EVM-compatible L2s).
Multi-Chain Support: Users can choose their preferred chain for NFT minting and EAS attestations.
Storage: IPFS via Lighthouse


Used for decentralized storage of species research data and NFT metadata.
Periodic exports of the entire species dataset are pinned to IPFS for public access.
AI Services


Perplexity API: Gathers unstructured web data for species research.
OpenAI API (GPT-4): Structures the collected data into the predefined JSON schema for the species table.
Deployment


Frontend: Vercel
Backend/Database: DigitalOcean (VM with PostgreSQL 14.17)
Blockchain: Smart contracts deployed on Base, Celo, Optimism, and Arbitrum (initially on testnets).

3.2 AI Research Process
The AI Research Process allows users to fund and trigger AI-driven data collection and structuring for unresearched tree species. This process is initiated via the frontend, orchestrated by the backend, and results in updated species data, an IPFS upload, and blockchain actions (EAS attestation and NFT minting).
3.2.1 Trigger Mechanism
User Action: On the species details page, users can click the “Fund This Tree’s Research” button for unresearched species.
API Call: The frontend submits a POST /fund-research request to the backend with the following payload:
 json
CopyEdit
{
  "taxon_id": "123",
  "wallet_address": "0x...",
  "chain": "base",
  "transaction_hash": "0x..."
}


taxon_id: Unique identifier of the species to research.
wallet_address: The user’s blockchain wallet address.
chain: The user’s chosen chain for NFT minting (e.g., "base", "celo", "optimism", "arbitrum").
transaction_hash: The hash of the transaction where the user funded the research.
3.2.2 AI Data Collection and Structuring
Perplexity API: The backend gathers unstructured web data about the species, using the taxon_id, species, and common_name as search terms.
OpenAI API (GPT-4): The unstructured data is passed to GPT-4, which structures it into a JSON object matching the species table schema (e.g., general_description, habitat, ecological_function).
Validation: The backend validates the structured JSON to ensure it meets the required format before proceeding.
3.2.3 Database and IPFS Storage
Database Update: The structured JSON is inserted or updated in the species table in PostgreSQL. The verification_status is set to unverified (manual review can verify later).
IPFS Upload: The same JSON is uploaded to IPFS via Lighthouse, and the resulting ipfs_cid is stored in the species table for that species.
3.2.4 Blockchain Actions
EAS Attestation: The backend uses ethers.js to interact with the EAS contract on the user’s chosen chain, attesting the ipfs_cid and taxon_id.
NFT Minting: The backend mints a Contreebution NFT (ERC-721) to the user’s wallet_address on the selected chain, using the ipfs_cid as part of the NFT metadata.
Database Logging: Minting details (transaction_hash, ipfs_cid) are stored in the contreebution_nfts table, and the user’s points are updated via the update_user_points trigger.
3.2.5 Response to Frontend
The backend returns the structured JSON, the ipfs_cid, and blockchain transaction details (e.g., EAS attestation UID, NFT token ID) to the frontend.
The frontend displays the research data and informs the user that their NFT has been minted.
3.2.6 Data Flow Diagram
css
CopyEdit
[User (Frontend)] → POST /fund-research → [Backend]
    ↓
[Backend] → Triggers AI Research → [Perplexity API] → [GPT-4]
    ↓
[Backend] → Structures JSON → Validates → Stores in PostgreSQL
    ↓
[Backend] → Uploads JSON to IPFS → Stores `ipfs_cid`
    ↓
[Backend] → EAS Attestation on selected chain
    ↓
[Backend] → Mints Contreebution NFT on selected chain
    ↓
[Backend] → Logs NFT details in `contreebution_nfts`
    ↓
[Backend] → Returns JSON, `ipfs_cid`, and blockchain details to [Frontend]


3.3 Multi-Chain Blockchain Setup
Treekipedia supports multiple EVM-compatible L2 networks (Base, Celo, Optimism, Arbitrum) to give users flexibility when minting NFTs and creating EAS attestations.
Smart Contracts:


ContreebutionNFT.sol (ERC-721) deployed on each chain.
EAS contracts are used directly from official deployments on each chain.
Chain Configurations:


Chain-specific RPC URLs, contract addresses, and EAS contract addresses are stored in backend/config/chains.js.
The frontend uses chains.ts to manage chain switching and wallet connections.
Blockchain Interactions:


All blockchain actions (EAS attestations, NFT minting) are handled by the backend using ethers.js.
The backend selects the appropriate provider and contract addresses based on the user’s chosen chain in the request.

3.4 Periodic Data Exports to IPFS
To promote openness, Treekipedia periodically exports the entire species table to IPFS.
Export Process:


A script (backend/scripts/export.js) exports the species table as a CSV file.
The CSV is pinned to IPFS via Lighthouse, and the CID is shared on the Treekipedia website or GitHub.
Exports are versioned (e.g., treekipedia_data_v1.0.csv) and updated monthly.
Future Automation:


Use node-cron to automate monthly exports.

3.5 Security and Authentication
API Security: Backend endpoints secured with API keys (API_KEY in .env).
Wallet Authentication: Frontend uses wallet connections (e.g., MetaMask via Wagmi) for user actions like funding research.
Private Keys: Blockchain interactions use a backend-managed private key (stored securely in .env) for signing transactions.

3.6 Codebase Structure
The codebase is modular, separating backend, frontend, and blockchain components:
Backend (backend/)


config/chains.js: Chain-specific configurations.
controllers/: API logic for species, Treederboard, and research.
models/: Database queries for species and Treederboard.
services/: AI research, IPFS, and blockchain logic.
routes/index.js: API route definitions.
server.js: Express.js server setup.
Frontend (frontend/)


components/: Reusable UI components (e.g., SearchForm.tsx).
pages/: Next.js pages (search, species, Treederboard).
lib/api.ts: API client for backend calls.
config/chains.ts: Frontend chain configurations.
Contracts (contracts/)


ContreebutionNFT.sol: ERC-721 contract for NFTs.
EASAttestation.sol: Custom EAS integration (if needed).
Scripts (scripts/)


deploy.js: Deploys contracts to all four chains.
Database (database/)


schema.sql: PostgreSQL schema for all tables.
seed.js: Optional seed script for initial data.

3.7 Dependencies and Tools
Programming Languages: JavaScript (Node.js, React/Next.js), TypeScript (frontend), Solidity (contracts)
Frameworks/Libraries: Express.js, Next.js, React, ethers.js, pg, dotenv, nodemon, Wagmi, node-cron
Databases: PostgreSQL 14.17
Blockchain: EAS, ERC-721, Base, Celo, Optimism, Arbitrum
Storage: IPFS via Lighthouse
APIs: Perplexity API, OpenAI API, Lighthouse API, Infura API
Tools: Hardhat, Vercel, DigitalOcean, Git, yarn

3.8 Future Extensibility
Option Sets: Standardize fields like conservation_status for consistency.
Blazegraph Integration: Enable advanced querying and RDF support for species data.

4. Database Design

4.1 Species Table
Table Name: species
Schema: public
Primary Key: taxon_id (text)
Owner: postgres
Fields (grouped for readability):
Taxonomic Fields
taxon_id TEXT NOT NULL – Unique identifier for the species (PK)
species VARCHAR(300) – Species name
family VARCHAR(300) – Taxonomic family
genus VARCHAR(300) – Taxonomic genus
subspecies TEXT – Subspecies name
specific_epithet VARCHAR(300) – Specific epithet
accepted_scientific_name TEXT – Accepted scientific name
synonyms TEXT – List of synonyms
Common Names and Locations
common_name TEXT – Common name(s)
common_countries TEXT – Countries where commonly found
countries_introduced TEXT – Countries where introduced
countries_invasive TEXT – Countries where invasive
countries_native TEXT – Native countries
Ecological Data
class VARCHAR(300) – Taxonomic class
taxonomic_order VARCHAR(300) – Taxonomic order
ecoregions TEXT – Ecoregions of occurrence
biomes TEXT – Biomes where found
habitat TEXT – Habitat description
forest_type TEXT – Type of forest habitat
wetland_type TEXT – Type of wetland habitat
urban_setting TEXT – Urban habitat details
elevation_ranges TEXT – Elevation ranges
compatible_soil_types TEXT – Compatible soil types
associated_species TEXT – Associated species
native_adapted_habitats TEXT – Adapted native habitats
agroforestry_use_cases TEXT – Agroforestry applications
successional_stage VARCHAR(300) – Successional stage
tolerances TEXT – Environmental tolerances
forest_layers TEXT – Forest layers occupied
Morphological Characteristics
growth_form VARCHAR(300) – Growth form (tree, shrub, etc.)
leaf_type VARCHAR(300)
deciduous_evergreen VARCHAR(300)
flower_color VARCHAR(300)
fruit_type VARCHAR(300)
bark_characteristics TEXT
maximum_height NUMERIC(10,2) – Max height in meters
maximum_diameter NUMERIC(10,2) – Max diameter in meters
lifespan VARCHAR(300) – Typical lifespan
maximum_tree_age INTEGER – Max age in years
Conservation and Management
conservation_status VARCHAR(300)
climate_change_vulnerability VARCHAR(300)
national_conservation_status TEXT
verification_status VARCHAR(300)
threats TEXT
timber_value TEXT
non_timber_products TEXT
cultural_significance TEXT
cultivars TEXT
nutritional_caloric_value TEXT
cultivation_details TEXT
stewardship_best_practices TEXT
planting_recipes TEXT
pruning_maintenance TEXT
disease_pest_management TEXT
fire_management TEXT
Scientific and Metadata
general_description TEXT
associated_media TEXT
ecological_function TEXT
default_image VARCHAR(300) – Default image URL
total_occurrences INTEGER
allometric_models TEXT
allometric_curve TEXT
reference_list TEXT
data_sources TEXT
ipfs_cid VARCHAR(300) – IPFS content identifier for the species
last_updated_date TIMESTAMP WITHOUT TIME ZONE
created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
Constraints
species_pkey: Primary key constraint on taxon_id

4.2 Treederboard Tables
Users Table
Table Name: users
Schema: public
Primary Key: id (serial)
Fields
id SERIAL PRIMARY KEY – Unique identifier
wallet_address TEXT UNIQUE NOT NULL – User’s blockchain wallet address
display_name TEXT
total_points INTEGER DEFAULT 0 – Total points
first_contribution_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
last_contribution_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
contribution_count INTEGER DEFAULT 0
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
Comments:
Stores user info and total accumulated points.
wallet_address is unique.
Tracks contribution_count and timestamps.

Contreebution NFTs Table
Table Name: contreebution_nfts
Schema: public
Primary Key: id (serial)
Fields
id SERIAL PRIMARY KEY – Unique identifier
global_id BIGINT UNIQUE NOT NULL DEFAULT nextval('global_id_seq') – Unique sequential identifier
taxon_id TEXT NOT NULL – References species.taxon_id
wallet_address TEXT NOT NULL – Wallet address of NFT recipient
points INTEGER DEFAULT 2 – Points awarded (default 2)
ipfs_cid TEXT – IPFS CID of NFT metadata
transaction_hash TEXT – Blockchain transaction hash
metadata JSONB – Additional NFT metadata
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
Comments:
Tracks all Contreebution NFTs minted for users.
taxon_id references the species table.
points default to 2.

4.3 Sequences
Sequence Name: global_id_seq
Increment: 1
Start: 0
Min Value: 0
Max Value: 9223372036854775807
Cache: 1
Purpose: Generates unique global_id values for contreebution_nfts.

4.4 Triggers and Functions
Function: update_user_points
Language: PL/pgSQL
Definition:
 sql
CopyEdit
CREATE OR REPLACE FUNCTION update_user_points()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (wallet_address, total_points, contribution_count, last_contribution_at)
  VALUES (NEW.wallet_address, NEW.points, 1, CURRENT_TIMESTAMP)
  ON CONFLICT (wallet_address) 
  DO UPDATE SET 
    total_points = users.total_points + NEW.points,
    contribution_count = users.contribution_count + 1,
    last_contribution_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


Purpose: Updates users table when a new NFT is inserted.
Trigger: trigger_update_user_points
Event: AFTER INSERT on contreebution_nfts
Execution: FOR EACH ROW
Function: Executes update_user_points

4.5 Indexes
Users Table: idx_users_wallet_address on wallet_address
Contreebution NFTs Table:
idx_contreebution_nfts_wallet_address on wallet_address
idx_contreebution_nfts_taxon_id on taxon_id
Species Table: Recommended indexes on taxon_id, common_name, and accepted_scientific_name for performance

5. Data Accessibility and Openness
To align with Treekipedia's open-source and collaborative ethos, the species data will be made publicly accessible through periodic exports to IPFS.

5.1 Periodic Data Exports
Process


A script (backend/scripts/export.js) exports the species table as a CSV file.
The CSV file is pinned to IPFS using Lighthouse, generating a unique CID for each export.
The team manually runs this script periodically (e.g., monthly) and shares the latest CID on the Treekipedia website or GitHub.
Export Details


Includes all fields from the species table, providing a complete snapshot.
Each export is versioned (e.g., treekipedia_data_v1.0.csv) to reflect updates.
Access


Users retrieve the CSV from IPFS using the CID.
Ensures decentralized, permanent access.

5.2 Future Enhancements
Automate the export process using a cron job.
Integrate with tools like DVC (Data Version Control) for more sophisticated versioning.
Expand exports to include Treederboard data or other tables as needed.

6. API Endpoints
The Express.js backend provides RESTful endpoints to interact with PostgreSQL.

6.1 Species Endpoints
GET /species?search=query
Returns species matching common_name or accepted_scientific_name.
GET /species/:taxon_id
Returns all fields for a species by taxon_id.
GET /species/suggest?query=partial
Returns up to 5 auto-complete suggestions.

6.2 Treederboard Endpoints
GET /treederboard
Returns users sorted by total_points.
POST /user/profile
Body: { "wallet_address": "0x...", "display_name": "Alice" }
Updates users.display_name.

6.3 Research and NFT Endpoints
POST /fund-research
Body: { "taxon_id": "123", "wallet_address": "0x...", "chain": "base", "transaction_hash": "0x..." }
Initiates the research and NFT minting process.
GET /user-nfts/:wallet_address
Returns all NFTs minted by a user.

7. Frontend Structure
The Next.js frontend focuses on usability and data display.

7.1 Pages
Search Page (/)
Search bar for species queries.
Results link to species pages.
Species Page (/species/[taxon_id])
Displays all species fields, grouped by category.
“Fund This Tree’s Research” button for unresearched species.
Treederboard Page (/treederboard)
Lists users with wallet_address, total_points, and contribution_count.

7.2 Components
SearchForm: Handles species search input with auto-complete.
SpeciesCard: Displays search result summaries.
SpeciesDetails: Renders full species data.
TreederboardTable: Shows contributor rankings.

8. Blockchain Integration
Contracts: ContreebutionNFT.sol deployed on each chain.
Metadata: Stored on IPFS via Lighthouse.
EAS: Attestations created post-NFT minting.

9. Authentication
API Key: Secures backend endpoints.
Wallet: Frontend uses wallet connections (MetaMask, etc.) for user actions.

10. Future Extensibility
Option Sets: Standardize fields like conservation_status.
Blazegraph: Integrate for advanced querying.

11. Deployment
Frontend: Vercel
Backend/Database: DigitalOcean (PostgreSQL 14.17)
Blockchain: Contracts on Base, Celo, Optimism, Arbitrum (testnets first)

12. Codebase Structure
A simplified folder/file structure:
csharp
CopyEdit
treekipedia-new/
├── backend/
│   ├── config/
│   │   └── chains.js          # Chain-specific configs (RPCs, contract addresses)
│   ├── controllers/
│   │   ├── species.js         # Species search, details, suggestions
│   │   ├── treederboard.js    # Treederboard/user profile logic
│   │   └── research.js        # Research funding, AI trigger, NFT minting
│   ├── models/
│   │   ├── species.js         # PostgreSQL species queries
│   │   └── treederboard.js    # PostgreSQL Treederboard queries
│   ├── services/
│   │   ├── aiResearch.js      # AI research logic (LLM calls, JSON structuring)
│   │   ├── ipfs.js            # IPFS upload logic
│   │   └── blockchain.js      # Blockchain interactions (EAS, NFT minting)
│   ├── routes/
│   │   └── index.js           # API route definitions
│   └── server.js              # Express.js server setup
├── frontend/
│   ├── components/
│   │   ├── SearchForm.tsx
│   │   ├── SpeciesCard.tsx
│   │   ├── SpeciesDetails.tsx
│   │   └── TreederboardTable.tsx
│   ├── pages/
│   │   ├── index.tsx
│   │   ├── species/
│   │   │   └── [taxon_id].tsx
│   │   └── treederboard.tsx
│   ├── lib/
│   │   └── api.ts
│   └── config/
│       └── chains.ts
├── contracts/
│   ├── ContreebutionNFT.sol
│   └── EASAttestation.sol
├── scripts/
│   └── deploy.js
└── database/
    ├── schema.sql
    └── seed.js


13. Dependencies, Tools, APIs, and Components
Programming Languages:


JavaScript (Node.js for backend, React/Next.js for frontend)
TypeScript (frontend)
Solidity (smart contracts)
Frameworks and Libraries:


Express.js (backend)
Next.js (frontend)
React (frontend)
ethers.js (blockchain interactions)
pg (PostgreSQL client)
dotenv (environment variables)
nodemon (development)
Wagmi (wallet connections & chain switching)
node-cron (scheduling)
Databases: PostgreSQL 14.17


Blockchain:


Ethereum Attestation Service (EAS)
ERC-721 (Contreebution NFTs)
Layer 2 networks: Base, Celo, Optimism, Arbitrum
Storage: IPFS via Lighthouse


APIs:


Perplexity API (AI-driven research)
OpenAI API (potential AI tasks)
Lighthouse API (IPFS pinning)
Infura API (blockchain data and RPC access)
Tools:


Hardhat (smart contract dev/deployment)
Vercel (frontend deployment)
DigitalOcean (backend/database hosting)
Git (version control)
yarn (package management)
Other:


MetaMask (user interactions)
Filecoin (potential funding/integration)

