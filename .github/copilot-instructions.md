# TickTick MCP Server - AI Agent Instructions

## Project Overview
**TickTick MCP Server** is a Model Context Protocol (MCP) implementation that exposes TickTick's task management API to AI agents. The server operates in two modes: **local stdio** (for Claude Desktop) and **remote SSE** (for multi-client deployment with OAuth2 authentication).

## Architecture

### Dual-Mode Transport Layer
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

**Key Files:**
- `ticktick_mcp/src/server.py` - FastMCP server with 22 MCP tools
- `ticktick_mcp/gateway.py` - OAuth2 client credentials gateway (remote mode only)
- `ticktick_mcp/src/ticktick_client.py` - TickTick API wrapper with auto token refresh
- `ticktick_mcp/cli.py` - CLI entry point with interactive auth setup

### OAuth Gateway (Remote Mode)
The gateway (`gateway.py`) provides OAuth2 client credentials flow for Claude Desktop's Custom Connector:
- `POST /oauth/token` - Issues JWT tokens (15min expiry, HMAC-SHA256 signed)
- `GET /sse` - Protected SSE endpoint (validates Bearer token, proxies to FastMCP on port 8000)
- `POST /messages` - Protected tool call endpoint
- `GET /health` - Status check

**Critical**: The gateway runs on port 8080, FastMCP on internal port 8000. Both must run simultaneously via `start-remote.sh`.

## Development Patterns

### MCP Tool Definition Pattern
All 22 tools in `server.py` follow this structure:
```python
@mcp.tool()
async def tool_name(param: str, optional_param: str = None) -> str:
    """Tool description with clear parameter documentation."""
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

**Key conventions:**
- All tools return `str` (formatted human-readable output)
- Global `ticktick` client is lazy-initialized
- Errors are caught and returned as strings (never raise exceptions to MCP layer)
- Helper functions like `format_task()` and `format_project()` format TickTick API responses

### Date Handling
TickTick uses ISO 8601 format: `YYYY-MM-DDThh:mm:ss+0000`
- Parsing: `datetime.fromisoformat(date_str.replace("Z", "+00:00"))`
- Timezone-aware comparisons with `datetime.now(timezone.utc)`
- Date validation happens in tools before API calls

### Task Filtering Pattern
Reusable filter functions in `server.py`:
```python
def _get_project_tasks_by_filter(projects, filter_func, filter_name):
    """Helper to filter tasks across all projects."""
    # Iterates closed projects, applies filter_func to each task
```

Used by: `get_tasks_due_today()`, `get_overdue_tasks()`, `get_tasks_by_priority()`, etc.

### Token Management
`TickTickClient` automatically refreshes expired tokens:
1. Detects 401 responses from API
2. Uses `refresh_token` to get new `access_token`
3. Updates `.env` file atomically (preserves all existing vars)
4. Retries original request with new token

**Important**: `_save_tokens_to_env()` preserves comments and formatting in `.env`.

## Build & Run Commands

### Local Development
```bash
# Initial setup (must run first)
uv venv && source .venv/bin/activate
uv pip install -e .

# Authenticate (creates .env with tokens)
uv run -m ticktick_mcp.cli auth

# Test configuration
python test_server.py

# Run local mode (stdio)
uv run -m ticktick_mcp.cli run

# Run remote mode (SSE) - single server
uv run -m ticktick_mcp.cli run --transport sse --host 0.0.0.0 --port 8080
```

### Remote Mode with OAuth Gateway
```bash
# Generate OAuth credentials (for Claude Desktop Custom Connector)
python generate-oauth-credentials.py

# Add to .env:
# MCP_OAUTH_CLIENTS=claude:generated_secret
# MCP_OAUTH_SIGNING_KEY=base64_key

# Start dual-server stack (FastMCP + OAuth Gateway)
./start-remote.sh

# OR use Docker
docker-compose up -d --build
```

### Testing
```bash
# Test local SSE server
python test_sse_server.py

# Test remote server
python test_sse_server.py --host your-server.com --port 8080

# Test OAuth token flow
curl -X POST http://localhost:8080/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"grant_type":"client_credentials","client_id":"claude","client_secret":"secret"}'
```

## Configuration

### Environment Variables (`.env`)
**Required for all modes:**
- `TICKTICK_CLIENT_ID` - From TickTick Developer Center
- `TICKTICK_CLIENT_SECRET` - OAuth2 app secret
- `TICKTICK_ACCESS_TOKEN` - Generated via `cli.py auth`
- `TICKTICK_REFRESH_TOKEN` - Generated via `cli.py auth`

**Optional (Dida365 Chinese version):**
- `TICKTICK_BASE_URL=https://api.dida365.com/open/v1`
- `TICKTICK_AUTH_URL=https://dida365.com/oauth/authorize`
- `TICKTICK_TOKEN_URL=https://dida365.com/oauth/token`

**Remote mode OAuth (for Claude Desktop):**
- `MCP_OAUTH_CLIENTS=client_id:secret` (comma-separated for multiple)
- `MCP_OAUTH_SIGNING_KEY=base64_encoded_key` (32+ bytes)
- `MCP_TOKEN_EXPIRY=900` (seconds, default 15min)
- `FASTMCP_SERVER_URL=http://127.0.0.1:8000` (internal routing)

### Claude Desktop Config
**Local mode (`claude_desktop_config.json`):**
```json
{
  "mcpServers": {
    "ticktick": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/ticktick-mcp", "-m", "ticktick_mcp.cli", "run"]
    }
  }
}
```

**Remote mode (Custom Connector UI):**
- Server URL: `https://ticktick.yourdomain.com/sse`
- OAuth Client ID: `claude` (from `MCP_OAUTH_CLIENTS`)
- OAuth Client Secret: `generated_secret` (from `MCP_OAUTH_CLIENTS`)

## Common Pitfalls

1. **Missing Authentication**: Running server without `.env` fails silently. Always run `uv run -m ticktick_mcp.cli auth` first.

2. **Port Conflicts in Remote Mode**: OAuth gateway (8080) and FastMCP (8000) must both run. Use `start-remote.sh` script, not individual commands.

3. **Token Expiry**: TickTick tokens expire. The client auto-refreshes, but initial auth requires valid `refresh_token`.

4. **Docker Health Checks**: Dockerfile health check uses `/health` endpoint (gateway), not `/sse`.

5. **Priority Values**: TickTick uses non-sequential integers: `{0: None, 1: Low, 3: Medium, 5: High}`.

6. **Date Formats**: Tools accept ISO 8601. Invalid formats return error strings (not exceptions).

## Security Considerations

- **OAuth Credentials**: `MCP_OAUTH_CLIENTS` are separate from TickTick app credentials
- **JWT Signing**: Short-lived tokens (15min) with HMAC-SHA256, prevents tampering
- **HTTPS Required**: Remote deployments must use reverse proxy (nginx/Caddy) with SSL
- **Environment Secrets**: Never commit `.env` files. Use Docker secrets or cloud secret managers in production

## Testing & Debugging

**Enable debug logging:**
```bash
uv run -m ticktick_mcp.cli run --debug
```

**Common debug checks:**
```bash
# Check TickTick API connectivity
python -c "from ticktick_mcp.src.ticktick_client import TickTickClient; print(TickTickClient().get_projects())"

# Verify OAuth clients configured
curl http://localhost:8080/health

# Test JWT validation
TOKEN=$(curl -X POST http://localhost:8080/oauth/token ... | jq -r .access_token)
curl -N -H "Authorization: Bearer $TOKEN" http://localhost:8080/sse
```

## Documentation References

- **README.md** - User-facing setup and usage
- **OAUTH_IMPLEMENTATION.md** - OAuth2 gateway technical details
- **DEPLOYMENT.md** - Production deployment (Docker, K8s, cloud providers)
- **MIGRATION.md** - Upgrading from local to remote mode
