#!/bin/bash

# Treekipedia Local Services Stop Script
# Stops all running local services

echo "============================================================"
echo "🛑 Stopping Treekipedia Local Services"
echo "============================================================"
echo ""

# Colors
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

stop_port() {
    local port=$1
    local service=$2

    if lsof -ti:$port >/dev/null 2>&1; then
        echo -e "${YELLOW}Stopping $service on port $port...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null
        echo -e "${GREEN}✅ $service stopped${NC}"
    else
        echo "ℹ️  No service running on port $port"
    fi
}

stop_port 5001 "Backend API"
stop_port 5002 "Location Predictor"
stop_port 3001 "Frontend"

echo ""
echo "============================================================"
echo "✅ All services stopped"
echo "============================================================"
