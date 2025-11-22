# OAuth2 Setup Quick Start Guide

This guide walks you through setting up OAuth2 authentication for Claude Desktop's Custom Connector.

## Prerequisites

- TickTick account with API credentials (see main README.md)
- Server with Docker and Docker Compose installed
- Domain name with SSL certificate (for production)

## Step 1: Generate OAuth Credentials

Run the credential generator script:

```bash
python generate-oauth-credentials.py
```

This will output something like:

```
✅ Generated OAuth2 Credentials

Add these to your .env file:
------------------------------------------------------------
MCP_OAUTH_CLIENTS=claude:xyzABC123_randomstring
MCP_OAUTH_SIGNING_KEY=dGVzdGluZ3NlY3JldGtleTE...
------------------------------------------------------------

For Claude Desktop Custom Connector, use:
------------------------------------------------------------
OAuth Client ID:     claude
OAuth Client Secret: xyzABC123_randomstring
------------------------------------------------------------
```

## Step 2: Configure Environment Variables

Add the generated credentials to your `.env` file:

```bash
# Copy example if you don't have .env yet
cp .env.example .env

# Edit .env and add the OAuth credentials
nano .env
```

Add these lines (use your generated values):

```env
# OAuth2 Gateway Configuration
MCP_OAUTH_CLIENTS=claude:xyzABC123_randomstring
MCP_OAUTH_SIGNING_KEY=dGVzdGluZ3NlY3JldGtleTE...
MCP_TOKEN_EXPIRY=900
FASTMCP_SERVER_URL=http://127.0.0.1:8000
```

## Step 3: Authenticate with TickTick

If you haven't already, authenticate to get your TickTick access tokens:

```bash
uv run -m ticktick_mcp.cli auth
```

This will update your `.env` file with:

- `TICKTICK_ACCESS_TOKEN`
- `TICKTICK_REFRESH_TOKEN`

## Step 4: Deploy with Docker

### Option A: Docker Compose (Recommended)

```bash
# Build and start the services
docker-compose up -d --build

# Check logs
docker-compose logs -f ticktick-mcp

# You should see:
# Starting TickTick MCP server stack...
# FastMCP Server: http://127.0.0.1:8000
# OAuth Gateway: http://0.0.0.0:8080
# Starting FastMCP SSE server on port 8000...
# Starting OAuth gateway on port 8080...
```

### Option B: Manual Docker

```bash
# Build the image
docker build -t ticktick-mcp .

# Run with environment file
docker run -d \
  --name ticktick-mcp \
  -p 8080:8080 \
  --env-file .env \
  ticktick-mcp

# Check logs
docker logs -f ticktick-mcp
```

## Step 5: Verify Deployment

Test the OAuth token endpoint:

```bash
# Replace with your client credentials
CLIENT_ID="claude"
CLIENT_SECRET="xyzABC123_randomstring"

# Request a token
curl -X POST http://localhost:8080/oauth/token \
  -H "Content-Type: application/json" \
  -d "{
    \"grant_type\": \"client_credentials\",
    \"client_id\": \"$CLIENT_ID\",
    \"client_secret\": \"$CLIENT_SECRET\"
  }"
```

Expected response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 900,
  "scope": "mcp:full"
}
```

Test the SSE endpoint with the token:

```bash
# Extract the token from the previous response
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Connect to SSE endpoint
curl -N -H "Authorization: Bearer $TOKEN" http://localhost:8080/sse
```

You should see MCP protocol JSON events streaming.

## Step 6: Configure Claude Desktop

1. Open Claude Desktop
2. Go to Settings → Custom Connectors (or similar)
3. Add a new connector:

   - **Name**: TickTick Tasks
   - **Description**: Manage TickTick via remote MCP
   - **Server URL**: `http://localhost:8080/sse` (or your domain)
   - **OAuth Client ID**: `claude`
   - **OAuth Client Secret**: `xyzABC123_randomstring` (your generated secret)

4. Save and test the connection

Claude will automatically:

- Request a bearer token from `/oauth/token`
- Use the token for all SSE and tool requests
- Refresh the token before expiry

## Step 7: Production Deployment

For production, you'll need:

### SSL/TLS Certificate

Use a reverse proxy like nginx or Caddy:

```nginx
server {
    listen 443 ssl http2;
    server_name ticktick.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

### Update Claude Desktop Config

Change the URL to use HTTPS:

```json
{
  "mcpServers": {
    "ticktick": {
      "url": "https://ticktick.yourdomain.com/sse",
      "oauth": {
        "clientId": "claude",
        "clientSecret": "xyzABC123_randomstring"
      }
    }
  }
}
```

## Troubleshooting

### Token endpoint returns 401

- Check `MCP_OAUTH_CLIENTS` format in `.env`
- Ensure no extra spaces in the `client_id:secret` pair
- Verify you're using the exact secret generated

### SSE endpoint returns 401

- Token may be expired (default: 15 minutes)
- Request a new token from `/oauth/token`
- Check that token is being sent in `Authorization: Bearer` header

### SSE endpoint returns 502

- FastMCP server not running
- Check logs: `docker logs ticktick-mcp-server`
- Verify `FASTMCP_SERVER_URL` is correct

### Health check shows 0 clients configured

- `MCP_OAUTH_CLIENTS` not set or empty
- Check `.env` file exists and is loaded
- Restart container: `docker-compose restart`

### Claude can't connect

- Verify firewall allows port 8080
- Test with curl from Claude's machine
- Check SSL certificate is valid (for HTTPS)
- Ensure domain resolves correctly

## Security Best Practices

1. **Rotate credentials regularly** (monthly recommended)
2. **Use strong secrets** (32+ characters, URL-safe)
3. **Never commit `.env`** to version control
4. **Use HTTPS in production** (not HTTP)
5. **Separate credentials per environment** (dev/staging/prod)
6. **Monitor token issuance** for unusual activity
7. **Keep signing key secret** and backed up

## Adding More Clients

To allow multiple clients (e.g., different AI providers):

```env
# Comma-separated list
MCP_OAUTH_CLIENTS=claude:secret1,copilot:secret2,custom:secret3
```

Each client gets their own credentials but shares the same MCP server.

## Support

For issues or questions:

- Check main [README.md](README.md)
- Review [OAUTH_IMPLEMENTATION.md](OAUTH_IMPLEMENTATION.md)
- Open an issue on GitHub
