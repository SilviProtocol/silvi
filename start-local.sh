#!/bin/bash

# Treekipedia Local Deployment Script
# Starts all required services for local development

set -e

echo "============================================================"
echo "🌳 Treekipedia Local Deployment"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    echo -e "${YELLOW}Stopping existing service on port $port...${NC}"
    lsof -ti:$port | xargs kill -9 2>/dev/null || true
    sleep 1
}

echo "📋 Step 1: Checking PostgreSQL..."
if brew services list | grep -q "postgresql@17.*started"; then
    echo -e "${GREEN}✅ PostgreSQL is running${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL not running. Starting...${NC}"
    brew services start postgresql@17
    sleep 2
fi
echo ""

echo "📋 Step 2: Starting Backend API (port 5001)..."
if check_port 5001; then
    echo -e "${YELLOW}Port 5001 is in use. Stopping existing process...${NC}"
    kill_port 5001
fi
cd "$SCRIPT_DIR/treekipedia/backend"
node server.js > /tmp/treekipedia-backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
echo "   Log: /tmp/treekipedia-backend.log"
echo ""

echo "📋 Step 3: Starting Location Predictor Service (port 5002)..."
echo -e "${YELLOW}⚠️  Using orchestrator/location_predictor_FIXED.py for habitat prediction${NC}"
if check_port 5002; then
    echo -e "${YELLOW}Port 5002 is in use. Stopping existing process...${NC}"
    kill_port 5002
fi
cd "$SCRIPT_DIR/orchestrator"
python3 location_predictor_FIXED.py > /tmp/location-predictor.log 2>&1 &
PREDICTOR_PID=$!
echo -e "${GREEN}✅ Location Predictor started (PID: $PREDICTOR_PID)${NC}"
echo "   Log: /tmp/location-predictor.log"
echo ""

echo "📋 Step 4: Starting Frontend (port 3001)..."
if check_port 3001; then
    echo -e "${YELLOW}Port 3001 is in use. Stopping existing process...${NC}"
    kill_port 3001
fi
cd "$SCRIPT_DIR/treekipedia/frontend"
npm run dev > /tmp/treekipedia-frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "${GREEN}✅ Frontend started (PID: $FRONTEND_PID)${NC}"
echo "   Log: /tmp/treekipedia-frontend.log"
echo ""

echo "⏳ Waiting for services to initialize..."
sleep 5
echo ""

echo "============================================================"
echo "🎉 All services started successfully!"
echo "============================================================"
echo ""
echo "📍 Service URLs:"
echo "   Frontend:           http://localhost:3001"
echo "   Backend API:        http://localhost:5001"
echo "   Location Predictor: http://localhost:5002"
echo ""
echo "📊 Process IDs:"
echo "   Backend:            $BACKEND_PID"
echo "   Location Predictor: $PREDICTOR_PID"
echo "   Frontend:           $FRONTEND_PID"
echo ""
echo "📝 Log files:"
echo "   Backend:            /tmp/treekipedia-backend.log"
echo "   Location Predictor: /tmp/location-predictor.log"
echo "   Frontend:           /tmp/treekipedia-frontend.log"
echo ""
echo "🛑 To stop all services:"
echo "   ./stop-local.sh"
echo "   OR manually: lsof -ti:5001 | xargs kill && lsof -ti:5002 | xargs kill && lsof -ti:3001 | xargs kill"
echo ""
echo "============================================================"
