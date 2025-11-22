# Migration Guide: Local to Remote MCP Server

This guide helps existing users understand the changes and migrate to remote deployment if desired.

## What Changed?

The TickTick MCP server now supports two modes:

1. **Local Mode (stdio)** - Original behavior, unchanged
2. **Remote Mode (SSE)** - New capability for hosting on servers

## For Existing Users

**Good news: Nothing breaks!** 

If you're already using the server with Claude Desktop in local mode, everything continues to work exactly as before. The default behavior is unchanged.

### No Action Required If:
- You use the server locally with Claude Desktop
- You run it via stdio transport (the default)
- Your configuration looks like this:
  ```json
  {
    "mcpServers": {
      "ticktick": {
        "command": "uv",
        "args": ["run", "-m", "ticktick_mcp.cli", "run"]
      }
    }
  }
  ```

## Why Remote Mode?

Remote mode (SSE transport) enables:

1. **Single Server, Multiple Clients**: Host once, connect from many AI clients
2. **Centralized Management**: One server with one set of credentials
3. **Docker Deployment**: Easy hosting on cloud servers
4. **Team Usage**: Share the server across your organization
5. **Simplified Setup**: Connect new clients without local installation

## When to Use Remote Mode?

Consider remote mode if you:

- Want to access TickTick from multiple AI providers
- Have a home server or cloud instance available
- Want to avoid setting up credentials on each device
- Need centralized access control and monitoring
- Want to deploy using Docker/Kubernetes

## Migration Steps

### Option 1: Keep Using Local Mode
Do nothing! Your existing setup continues to work.

### Option 2: Try Remote Mode Locally

1. **Test the server in SSE mode**:
   ```bash
   ./start-remote.sh
   ```

2. **Verify it works**:
   ```bash
   python test_sse_server.py
   ```

3. **Update Claude Desktop config** to connect to local SSE server:
   ```json
   {
     "mcpServers": {
       "ticktick": {
         "url": "http://localhost:8080/sse"
       }
     }
   }
   ```

4. **Restart Claude Desktop**

### Option 3: Deploy to Remote Server

1. **Complete authentication locally** (if not already done):
   ```bash
   uv run -m ticktick_mcp.cli auth
   ```

2. **Copy your `.env` file to the server**:
   ```bash
   scp .env user@your-server:/path/to/ticktick-mcp/
   ```

3. **On the server, start with Docker**:
   ```bash
   docker-compose up -d
   ```

4. **Update all clients to point to the remote server**:
   ```json
   {
     "mcpServers": {
       "ticktick": {
         "url": "http://your-server:8080/sse"
       }
     }
   }
   ```

5. **Add HTTPS** (recommended for production) - see [DEPLOYMENT.md](DEPLOYMENT.md)

## Comparison

| Feature | Local Mode (stdio) | Remote Mode (SSE) |
|---------|-------------------|-------------------|
| Setup Complexity | Simple | Moderate |
| Single Client | ✅ | ✅ |
| Multiple Clients | ❌ | ✅ |
| Requires Server | ❌ | ✅ |
| Docker Support | ❌ | ✅ |
| Network Access | Local only | Local or Remote |
| Authentication | Per-device | Centralized |

## Configuration Reference

### Local Mode (stdio)
```bash
# Run server
uv run -m ticktick_mcp.cli run

# Claude Desktop config
{
  "mcpServers": {
    "ticktick": {
      "command": "uv",
      "args": ["run", "-m", "ticktick_mcp.cli", "run"]
    }
  }
}
```

### Remote Mode (SSE) - Local
```bash
# Run server
uv run -m ticktick_mcp.cli run --transport sse --host 0.0.0.0 --port 8080

# Claude Desktop config
{
  "mcpServers": {
    "ticktick": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

### Remote Mode (SSE) - Docker
```bash
# Run server
docker-compose up -d

# Claude Desktop config
{
  "mcpServers": {
    "ticktick": {
      "url": "http://your-server:8080/sse"
    }
  }
}
```

## Troubleshooting

### "Server not responding" in remote mode
1. Check if server is running: `docker ps` or `ps aux | grep ticktick`
2. Test connectivity: `python test_sse_server.py --host your-server`
3. Check firewall: Ensure port 8080 is open
4. Verify credentials: Check Docker logs for auth errors

### "Want to switch back to local mode"
Just revert your Claude Desktop config to use the stdio command instead of URL.

## Getting Help

- **General Questions**: See [README.md](README.md)
- **Deployment Help**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Issues**: https://github.com/marco308/ticktick-mcp/issues

## Security Notes

When using remote mode:

1. **Local Testing**: `http://localhost:8080/sse` is fine for testing
2. **Remote Deployment**: ALWAYS use HTTPS in production
3. **Access Control**: Use firewall rules to restrict access
4. **Credentials**: Keep your `.env` file secure, never commit it

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed security best practices.
