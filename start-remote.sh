#!/bin/bash
# Quick start script for running TickTick MCP server in remote mode

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}TickTick MCP Server - Quick Start (Remote Mode)${NC}"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please run authentication first:"
    echo "  uv run -m ticktick_mcp.cli auth"
    exit 1
fi

# Check if required environment variables are set
source .env
if [ -z "$TICKTICK_ACCESS_TOKEN" ]; then
    echo -e "${RED}Error: TICKTICK_ACCESS_TOKEN not found in .env file!${NC}"
    echo "Please run authentication first:"
    echo "  uv run -m ticktick_mcp.cli auth"
    exit 1
fi

# Default values
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

echo -e "${YELLOW}Starting TickTick MCP server with SSE transport...${NC}"
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  Access URL: http://$HOST:$PORT/sse"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Start the server
exec uv run -m ticktick_mcp.cli run --transport sse --host "$HOST" --port "$PORT"
