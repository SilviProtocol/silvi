#!/bin/bash
# Google Cloud Authentication Script
# This script will open your browser for authentication

echo "======================================================================"
echo "GOOGLE CLOUD AUTHENTICATION"
echo "======================================================================"
echo ""
echo "Step 1: Authenticating with your Google account..."
echo "This will open your browser. Please sign in with your Google account."
echo ""

# Authenticate user
gcloud auth login

echo ""
echo "Step 2: Setting up Application Default Credentials..."
echo "This is needed for Earth Engine Python API to work."
echo ""

# Setup application default credentials (needed for Earth Engine)
gcloud auth application-default login

echo ""
echo "======================================================================"
echo "ENABLING SERVICES"
echo "======================================================================"
echo ""

# Enable Earth Engine API
echo "Enabling Earth Engine API..."
gcloud services enable earthengine.googleapis.com

# Enable other useful services
echo "Enabling Cloud Storage API..."
gcloud services enable storage-api.googleapis.com

echo "Enabling BigQuery API..."
gcloud services enable bigquery.googleapis.com

echo ""
echo "======================================================================"
echo "✅ AUTHENTICATION COMPLETE!"
echo "======================================================================"
echo ""
echo "Next step: Test Earth Engine connection"
echo "Run: python3 test_ee_with_project.py"
echo ""
