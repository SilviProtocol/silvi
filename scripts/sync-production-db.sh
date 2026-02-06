#!/bin/bash

# Treekipedia Production Database Sync Script
# This script downloads the production database from Digital Ocean and imports it locally

set -e  # Exit on error

# Configuration
VM_IP="167.172.143.162"
VM_USER="root"  # Change this if you use a different user
DB_NAME="treekipedia"
DUMP_FILE="treekipedia_production_$(date +%Y%m%d_%H%M%S).sql"
LOCAL_DB="treekipedia"

echo "🌳 Treekipedia Database Sync"
echo "=============================="
echo ""
echo "VM: $VM_USER@$VM_IP"
echo "Database: $DB_NAME"
echo ""

# Step 1: Test SSH connection
echo "Step 1: Testing SSH connection..."
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$VM_USER@$VM_IP" exit 2>/dev/null; then
    echo "✅ SSH connection successful"
else
    echo "❌ SSH connection failed"
    echo ""
    echo "Please ensure:"
    echo "1. You have SSH access to the VM"
    echo "2. Your SSH key is added to the VM"
    echo "3. Run: ssh-copy-id $VM_USER@$VM_IP"
    echo ""
    echo "Or set up SSH keys:"
    echo "  ssh-keygen -t rsa -b 4096 -C 'your_email@example.com'"
    echo "  ssh-copy-id $VM_USER@$VM_IP"
    exit 1
fi

# Step 2: Create database dump on VM
echo ""
echo "Step 2: Creating database dump on VM..."
ssh "$VM_USER@$VM_IP" "pg_dump -U postgres $DB_NAME > /tmp/$DUMP_FILE"
echo "✅ Database dump created on VM"

# Step 3: Download dump file
echo ""
echo "Step 3: Downloading dump file..."
scp "$VM_USER@$VM_IP:/tmp/$DUMP_FILE" "./$DUMP_FILE"
echo "✅ Dump file downloaded: $DUMP_FILE"

# Step 4: Clean up remote dump file
echo ""
echo "Step 4: Cleaning up remote dump file..."
ssh "$VM_USER@$VM_IP" "rm /tmp/$DUMP_FILE"
echo "✅ Remote dump file removed"

# Step 5: Drop and recreate local database
echo ""
echo "Step 5: Preparing local database..."
/opt/homebrew/bin/dropdb "$LOCAL_DB" 2>/dev/null || echo "Database doesn't exist, creating new..."
/opt/homebrew/bin/createdb "$LOCAL_DB"
echo "✅ Local database ready"

# Step 6: Import dump to local database
echo ""
echo "Step 6: Importing data to local database..."
/opt/homebrew/bin/psql "$LOCAL_DB" < "./$DUMP_FILE"
echo "✅ Data imported successfully"

# Step 7: Verify import
echo ""
echo "Step 7: Verifying import..."
SPECIES_COUNT=$(/opt/homebrew/bin/psql -t "$LOCAL_DB" -c "SELECT COUNT(*) FROM species;")
IMAGES_COUNT=$(/opt/homebrew/bin/psql -t "$LOCAL_DB" -c "SELECT COUNT(*) FROM images;" 2>/dev/null || echo "0")
echo "✅ Import verified:"
echo "   - Species: $SPECIES_COUNT"
echo "   - Images: $IMAGES_COUNT"

# Cleanup
echo ""
echo "Step 8: Cleanup..."
echo "Keep dump file? (y/n) [default: n]"
read -r KEEP_DUMP
if [[ "$KEEP_DUMP" != "y" ]]; then
    rm "./$DUMP_FILE"
    echo "✅ Dump file removed"
else
    echo "✅ Dump file saved: $DUMP_FILE"
fi

echo ""
echo "🎉 Database sync complete!"
echo ""
echo "You can now:"
echo "  - Test queries: psql $LOCAL_DB"
echo "  - Start local backend: cd treekipedia/backend && node server.js"
echo "  - View data at: http://localhost:3000"
