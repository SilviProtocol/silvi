### Launch Checklist

### Payment System Setup

- [x]  Payment contract created to accept exactly 3 USDC and require a taxon_id on Celo, Base, Arbitrum, and Optimism
- [ ]  Payment contract deployed on Celo, Base, Arbitrum, and Optimism with contract addresses recorded
- [ ]  Frontend payment flow configured to detect the user’s connected chain and ensure it’s supported (Celo, Base, Arbitrum, or Optimism)
- [x]  User prompted to approve the payment contract to spend 3 USDC and send 3 USDC with the taxon_id in the frontend
- [x]  Transaction confirmation handled in the frontend, displaying "Processing started" and managing errors (e.g., insufficient balance, unsupported chain)
- [ ]  Payment contract addresses stored in the frontend configuration for each chain
- [ ]  Infura webhooks set up for each chain to monitor the SponsorshipReceived event from the payment contract
- [ ]  Backend /webhook endpoint implemented to receive and process event data from Infura
- [ ]  Event data (sender, taxon_id, amount, transaction_hash, chain) extracted and validated in the backend
- [ ]  scientific_name fetched from the database using the taxon_id in the backend
- [ ]  Existing POST /research/fund-research endpoint called with taxon_id, wallet_address, chain, transaction_hash, ipfs_cid, and scientific_name
- [ ]  Security (e.g., secret token or signature verification) added to the /webhook endpoint
- [ ]  Database table (e.g., sponsorships) created to track payment and research status with fields: taxon_id, wallet_address, chain, transaction_hash, status, nft_token_id
- [ ]  New sponsorship records inserted with status set to "pending" upon receiving the webhook event
- [ ]  Sponsorship records updated to status "completed" and nft_token_id added after fund-research API completes
- [ ]  End-to-end flow tested: user clicks "Sponsor this Species" → payment sent → event emitted → backend notified → research triggered → database updated → user can view status and NFT


### Frontend Polish

- [ ]  About page updated with the latest information
- [ ]  Research process ensured to work consistently without getting stuck (investigate issue with large common names)
- [ ]  Display name change function fixed on the profile page
- [ ]  Styling updates made for readability and consistency across the entire site

---

### Wishlist

### Mass Funding Mechanism

- [ ]  Mass funding page created where users can enter a dollar amount (rounded to the nearest multiple of $3)
- [ ]  Dynamic table generated with rows equal to the number of trees (e.g., 10 rows for $30)
- [ ]  "Fund Random Trees" button added to auto-select unresearched trees for unassigned rows
- [ ]  Manual selection enabled via a search bar with autocomplete for each row (by name, region, or ecological role)
- [ ]  Funding list updated with selected trees and a counter (e.g., "7/10 trees selected")
- [ ]  Confirmation screen added for users to review the table and total cost before funding
- [ ]  Smart contract updated to support batch minting of multiple NFTs in one transaction
- [ ]  Metadata for each NFT set to "Research Pending" initially, updated post-research
- [ ]  Research tasks queued for each minted tree
- [ ]  Progress tracker added to the user’s profile, showing research status (e.g., "Pending," "In Progress," "Completed") for each tree
- [ ]  Tree selection conflicts handled (e.g., reserving trees for auto-selection)
- [ ]  High gas costs mitigated (e.g., using Layer 2 networks, optimizing the minting function)
- [ ]  Research queue delays managed (e.g., scalable task queue, estimated completion times)
- [ ]  UI usability improved for mobile (e.g., responsive design, tooltips)
- [ ]  Research failures handled (e.g., retries, marking as "failed," notifying users)
- [ ]  Database load optimized (e.g., indexing, connection pooling)

### Email Collection and Profile Update

- [ ]  Popup added to collect user emails (e.g., "Signup for updates")
- [ ]  Email field added to the profile page
- [ ]  email column added to the users table in the PostgreSQL database