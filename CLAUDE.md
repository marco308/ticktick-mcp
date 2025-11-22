# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TickTick MCP Server is a Model Context Protocol implementation that exposes TickTick's task management API to AI agents. It operates in two modes: **local stdio** (for Claude Desktop) and **remote SSE** (for multi-client deployment with OAuth2 authentication).

## Build & Run Commands

```bash
# Initial setup
uv venv && source .venv/bin/activate
uv pip install -e .

# Authenticate with TickTick (creates .env with tokens)
uv run -m ticktick_mcp.cli auth

# Test configuration
python test_server.py

# Run local mode (stdio)
uv run -m ticktick_mcp.cli run

# Run remote mode with OAuth gateway (Docker)
docker-compose up -d --build

# Run remote mode locally (starts FastMCP + OAuth Gateway)
./start-remote.sh

# Test SSE server
python test_sse_server.py
python test_sse_server.py --host your-server.com --port 8080

# Debug mode
uv run -m ticktick_mcp.cli run --debug
```

## Architecture

```
Local Mode (stdio):        Remote Mode (SSE):
Claude Desktop             Multiple AI Clients
    ↓                           ↓
stdio transport            OAuth Gateway (port 8080)
    ↓                       ↓         ↓
FastMCP Server          JWT Auth   SSE Proxy
    ↓                           ↓
TickTickClient → TickTick API
```

### Key Components

- **ticktick_mcp/src/server.py** - FastMCP server with 22 MCP tools. All tools return `str` and use lazy-initialized global `ticktick` client
- **ticktick_mcp/gateway.py** - OAuth2 client credentials gateway for remote mode (issues JWT tokens, validates Bearer auth)
- **ticktick_mcp/src/ticktick_client.py** - TickTick API wrapper with automatic token refresh and atomic `.env` updates
- **ticktick_mcp/cli.py** - CLI entry point with `auth` and `run` commands
- **start-remote.sh** - Starts dual-server stack (FastMCP on port 8000, OAuth Gateway on port 8080)

### OAuth Gateway Endpoints (Remote Mode)

- `POST /oauth/token` - Issues JWT tokens (15min expiry, HMAC-SHA256 signed)
- `GET /sse` - Protected SSE endpoint (validates Bearer token, proxies to FastMCP)
- `POST /messages` - Protected tool call endpoint
- `GET /health` - Status check

## MCP Tool Pattern

All tools in `server.py` follow this structure:

```python
@mcp.tool()
async def tool_name(param: str, optional_param: str = None) -> str:
    """Tool description."""
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client..."
    try:
        result = ticktick.api_call(param, optional_param)
        if 'error' in result:
            return f"Error: {result['error']}"
        return format_output(result)
    except Exception as e:
        logger.error(f"Error in tool_name: {e}")
        return f"Error: {str(e)}"
```

- Errors returned as strings (never raise exceptions to MCP layer)
- Helper functions `format_task()` and `format_project()` format API responses

## Environment Variables

**Required (all modes):**
- `TICKTICK_CLIENT_ID`, `TICKTICK_CLIENT_SECRET` - From TickTick Developer Center
- `TICKTICK_ACCESS_TOKEN`, `TICKTICK_REFRESH_TOKEN` - Generated via `cli.py auth`

**Remote mode OAuth:**
- `MCP_OAUTH_CLIENTS=client_id:secret` (comma-separated for multiple clients)
- `MCP_OAUTH_SIGNING_KEY=base64_encoded_key`
- `MCP_TOKEN_EXPIRY=900` (seconds, default 15min)

## Common Pitfalls

1. **Port conflicts in remote mode**: OAuth gateway (8080) and FastMCP (8000) must both run. Use `start-remote.sh`, not individual commands
2. **Priority values**: TickTick uses non-sequential integers: `{0: None, 1: Low, 3: Medium, 5: High}`
3. **Date formats**: Tools accept ISO 8601 (`YYYY-MM-DDThh:mm:ss+0000`). Invalid formats return error strings
4. **Token refresh**: `TickTickClient` auto-refreshes expired tokens and updates `.env` atomically
