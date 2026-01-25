#!/bin/bash

# JobForge AI - Local Setup Validation Script
# This script validates all prerequisites before starting the application

set -e

echo "🔍 JobForge AI - Setup Validation"
echo "=================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Flags
ALL_GOOD=true

# Check 1: Python 3.13+
echo -n "✓ Checking Python 3.13+... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -ge 11 ]]; then
        echo -e "${GREEN}✓ Found Python $PYTHON_VERSION${NC}"
    else
        echo -e "${RED}✗ Python 3.11+ required (found $PYTHON_VERSION)${NC}"
        ALL_GOOD=false
    fi
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    ALL_GOOD=false
fi

# Check 2: Poetry
echo -n "✓ Checking Poetry... "
if command -v poetry &> /dev/null; then
    POETRY_VERSION=$(poetry --version | awk '{print $NF}')
    echo -e "${GREEN}✓ Found Poetry $POETRY_VERSION${NC}"
else
    echo -e "${RED}✗ Poetry not found. Install: curl -sSL https://install.python-poetry.org | python3 -${NC}"
    ALL_GOOD=false
fi

# Check 3: Docker
echo -n "✓ Checking Docker... "
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    echo -e "${GREEN}✓ Found Docker $DOCKER_VERSION${NC}"
else
    echo -e "${RED}✗ Docker not found. Install Rancher Desktop or Docker Desktop${NC}"
    ALL_GOOD=false
fi

# Check 4: Docker Daemon Running
echo -n "✓ Checking Docker daemon... "
if docker ps &> /dev/null; then
    echo -e "${GREEN}✓ Docker daemon is running${NC}"
else
    echo -e "${YELLOW}⚠ Docker daemon not running. Start Rancher Desktop or Docker Desktop${NC}"
    ALL_GOOD=false
fi

# Check 5: Docker socket
echo -n "✓ Checking Docker socket... "
if [[ -S "$HOME/.rd/docker.sock" ]]; then
    echo -e "${GREEN}✓ Found Rancher Desktop socket${NC}"
    export DOCKER_HOST=unix://$HOME/.rd/docker.sock
elif [[ -S "/var/run/docker.sock" ]]; then
    echo -e "${GREEN}✓ Found Docker Desktop socket${NC}"
    export DOCKER_HOST=unix:///var/run/docker.sock
else
    echo -e "${YELLOW}⚠ Docker socket not found. Make sure Docker is running${NC}"
    ALL_GOOD=false
fi

# Check 6: .env file
echo -n "✓ Checking .env file... "
if [[ -f ".env" ]]; then
    echo -e "${GREEN}✓ .env file found${NC}"
    
    # Check if OpenAI key is set
    if grep -q "OPENAI_API_KEY=sk-" .env; then
        echo -e "  ${GREEN}✓ OpenAI API key is configured${NC}"
    else
        echo -e "  ${YELLOW}⚠ OpenAI API key not configured. Update .env file${NC}"
        echo -e "  ${YELLOW}  Get key from: https://platform.openai.com/api-keys${NC}"
    fi
else
    echo -e "${RED}✗ .env file not found. Create one using the template in local_run.md${NC}"
    ALL_GOOD=false
fi

# Check 7: Poetry dependencies
echo -n "✓ Checking Poetry dependencies... "
if [[ -f "poetry.lock" ]]; then
    echo -e "${GREEN}✓ poetry.lock found${NC}"
else
    echo -e "${YELLOW}⚠ poetry.lock not found. Run: poetry install --no-root${NC}"
fi

# Check 8: Available Ports
echo -n "✓ Checking available ports... "
PORTS_AVAILABLE=true

for PORT in 8000 5432 6379; do
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${YELLOW}⚠ Port $PORT is already in use${NC}"
        PORTS_AVAILABLE=false
    fi
done

if [[ "$PORTS_AVAILABLE" == true ]]; then
    echo -e "${GREEN}✓ Ports 8000, 5432, 6379 are available${NC}"
fi

echo ""
echo "=================================="

# Summary
if [[ "$ALL_GOOD" == true ]]; then
    echo -e "${GREEN}✅ All checks passed! Ready to start.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Update .env with your OpenAI API key (if not done)"
    echo "  2. cd infra"
    echo "  3. docker-compose up -d"
    echo "  4. Open http://localhost:8000/docs"
    exit 0
else
    echo -e "${RED}❌ Some checks failed. Please fix the issues above.${NC}"
    exit 1
fi
