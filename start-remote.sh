#!/bin/bash
# Quick start script for running TickTick MCP server in remote mode with OAuth gateway

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}TickTick MCP Server - OAuth Gateway Mode${NC}"
echo ""

# Check if required environment variables are set (works with both .env file and docker env vars)
if [ -z "$TICKTICK_ACCESS_TOKEN" ]; then
    echo -e "${RED}Error: TICKTICK_ACCESS_TOKEN not set!${NC}"
    echo "Please set TICKTICK_ACCESS_TOKEN environment variable or run authentication first:"
    echo "  uv run -m ticktick_mcp.cli auth"
    exit 1
fi

# Check OAuth configuration
if [ -z "$MCP_OAUTH_CLIENTS" ]; then
    echo -e "${RED}Error: MCP_OAUTH_CLIENTS not configured!${NC}"
    echo "Please set MCP_OAUTH_CLIENTS environment variable."
    echo "Example: MCP_OAUTH_CLIENTS=claude:your_secret_here"
    exit 1
fi

if [ -z "$MCP_OAUTH_SIGNING_KEY" ]; then
    echo -e "${YELLOW}Warning: MCP_OAUTH_SIGNING_KEY not set. Generating temporary key...${NC}"
    echo "For production, set a persistent key in .env to survive restarts."
fi

# Default values
GATEWAY_PORT="${GATEWAY_PORT:-8080}"
FASTMCP_PORT="${FASTMCP_PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo -e "${YELLOW}Starting TickTick MCP server stack...${NC}"
echo "  FastMCP Server: http://127.0.0.1:$FASTMCP_PORT"
echo "  OAuth Gateway: http://$HOST:$GATEWAY_PORT"
echo "  SSE Endpoint: http://$HOST:$GATEWAY_PORT/sse"
echo "  Token Endpoint: http://$HOST:$GATEWAY_PORT/oauth/token"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the servers${NC}"
echo ""

# Start FastMCP server in background
echo "Starting FastMCP SSE server on port $FASTMCP_PORT..."
# Use python directly in container (uv not installed in image)
python -m ticktick_mcp.cli run --transport sse --host 127.0.0.1 --port "$FASTMCP_PORT" &
FASTMCP_PID=$!

# Give FastMCP a moment to start
sleep 2

# Start OAuth gateway in foreground
echo "Starting OAuth Authorization Code gateway on port $GATEWAY_PORT..."
export FASTMCP_SERVER_URL="http://127.0.0.1:$FASTMCP_PORT"
exec python -m ticktick_mcp.oauth_authorization_gateway

# Cleanup function for graceful shutdown
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $FASTMCP_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM
