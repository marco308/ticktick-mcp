# OAuth2 Client Credentials Implementation Summary

## Overview

Implemented a minimal OAuth2 client credentials gateway for TickTick MCP server to enable Claude Desktop's Custom Connector OAuth authentication.

## Changes Made

### 1. New Gateway Module (`ticktick_mcp/gateway.py`)

Created a FastAPI-based OAuth2 gateway that provides:

- **POST `/oauth/token`** - Issues JWT bearer tokens
  - Validates client credentials (client_id/client_secret)
  - Supports Basic Auth and form body authentication
  - Returns signed JWT tokens with configurable expiry (default: 15 minutes)
- **GET `/sse`** - Protected SSE endpoint
  - Validates Bearer tokens from Authorization header
  - Proxies authenticated requests to internal FastMCP server
- **POST `/messages`** - Protected tool call endpoint
  - Same token validation as SSE endpoint
  - Forwards tool invocations to FastMCP server
- **GET `/health`** - Health check endpoint
  - Returns gateway status and configuration info

### 2. Updated Dependencies (`requirements.txt`)

Added:

- `fastapi>=0.115.0,<1.0.0` - Web framework for gateway
- `pyjwt>=2.9.0,<3.0.0` - JWT token creation/validation
- `cryptography>=43.0.0,<44.0.0` - Cryptographic operations for JWT
- `httpx>=0.27.0,<1.0.0` - Async HTTP client for proxying requests

### 3. Removed Per-Tool Authentication (`ticktick_mcp/src/server.py`)

- Removed `API_KEYS` configuration
- Removed `_authorize()` and `_auth_error()` functions
- Removed `api_key: str = None` parameter from all 22 tool functions
- Removed all authorization checks from tool implementations

Authentication is now handled entirely at the gateway level, not per-tool.

### 4. Updated Docker Configuration

**`docker-compose.yml`**:

- Replaced `MCP_SERVER_API_KEYS` with OAuth environment variables:
  - `MCP_OAUTH_CLIENTS` - Comma-separated client_id:secret pairs
  - `MCP_OAUTH_SIGNING_KEY` - Base64 JWT signing key
  - `MCP_TOKEN_EXPIRY` - Token lifetime in seconds (default: 900)
  - `FASTMCP_SERVER_URL` - Internal FastMCP server URL

**`Dockerfile`**:

- Updated health check to use `/health` endpoint instead of `/sse`
- Changed entry point to use `start-remote.sh` script

**`start-remote.sh`**:

- Starts FastMCP server on internal port 8000
- Starts OAuth gateway on public port 8080
- Validates OAuth configuration on startup
- Provides graceful shutdown handling

### 5. Environment Configuration (`.env.example`)

Added OAuth section with:

- Instructions for generating client credentials
- JWT signing key generation command
- Token expiry configuration
- FastMCP server URL (for gateway-to-server communication)

### 6. Documentation Updates (`README.md`)

Replaced legacy authentication section with comprehensive OAuth2 guide:

- **Setup Steps**: How to generate credentials and configure the server
- **Claude Desktop Configuration**: Exact steps for Custom Connector setup
- **Architecture Diagram**: Visual flow of OAuth token exchange
- **Security Features**: JWT signing, token expiry, credential separation
- **Quick Validation Steps**: Testing token endpoint, SSE streaming, health checks
- **Troubleshooting**: Common issues and solutions

### 7. Credential Generator Script (`generate-oauth-credentials.py`)

Created utility script that:

- Generates cryptographically secure client credentials
- Creates base64-encoded JWT signing keys
- Outputs formatted .env entries
- Provides security best practices

## Architecture

```
Claude Desktop
    │
    ├─► POST /oauth/token (client_id, client_secret)
    │   ├─ Validates credentials against MCP_OAUTH_CLIENTS
    │   └─ Returns signed JWT (expires in 15 min)
    │
    ├─► GET /sse (Authorization: Bearer <jwt>)
    │   ├─ Validates JWT signature & expiry
    │   └─ Proxies to FastMCP on port 8000
    │
    └─► POST /messages (Authorization: Bearer <jwt>)
        ├─ Validates JWT signature & expiry
        └─ Proxies tool calls to FastMCP

OAuth Gateway (port 8080)
    └─► FastMCP Server (port 8000)
            └─► TickTick API
```

## Security Model

1. **Credential Separation**: OAuth client credentials are separate from TickTick API credentials
2. **JWT Signing**: HMAC-SHA256 prevents token tampering
3. **Short Expiry**: 15-minute tokens limit exposure window
4. **Bearer Token**: Standard OAuth2 pattern, widely supported
5. **Multiple Clients**: Support for multiple client_id:secret pairs

## Claude Desktop Integration

In Claude's Custom Connector UI:

- **Server URL**: `https://ticktick.yourdomain.com/sse`
- **OAuth Client ID**: `claude` (from MCP_OAUTH_CLIENTS)
- **OAuth Client Secret**: Generated secret value

Claude automatically:

1. Requests token from `/oauth/token` on connection
2. Includes `Authorization: Bearer <token>` in all requests
3. Refreshes token before expiry

## Migration Path

For existing deployments:

1. Generate OAuth credentials: `python generate-oauth-credentials.py`
2. Add to `.env` file: `MCP_OAUTH_CLIENTS` and `MCP_OAUTH_SIGNING_KEY`
3. Rebuild Docker image: `docker-compose up -d --build`
4. Update Claude Desktop config with OAuth Client ID/Secret
5. Old per-tool `api_key` parameters are removed (breaking change)

## Benefits

- ✅ Native Claude Desktop Custom Connector support
- ✅ Standard OAuth2 client credentials flow
- ✅ No per-tool authentication parameters
- ✅ Automatic token refresh
- ✅ Production-ready security model
- ✅ Multiple client support
- ✅ Easy credential rotation

## Files Modified

- `ticktick_mcp/gateway.py` (new)
- `ticktick_mcp/src/server.py` (removed auth code)
- `requirements.txt` (added dependencies)
- `docker-compose.yml` (OAuth env vars)
- `Dockerfile` (gateway entry point)
- `start-remote.sh` (dual-server startup)
- `.env.example` (OAuth section)
- `README.md` (OAuth documentation)
- `generate-oauth-credentials.py` (new utility)

## Next Steps (Optional)

1. **Rate Limiting**: Add per-client rate limits in gateway
2. **Structured Logging**: JSON logs with client_id, request_id
3. **Token Rotation**: Support for key rotation without downtime
4. **Scope-based Auth**: Restrict certain tools to specific clients
5. **Metrics**: Export token issuance, validation metrics
