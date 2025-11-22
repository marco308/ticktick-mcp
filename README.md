# TickTick MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for TickTick that enables interacting with your TickTick task management system directly through Claude and other MCP clients.

**Now supports both local (stdio) and remote (SSE) deployment modes!** 🚀

> 📖 **New to remote mode?** See [MIGRATION.md](MIGRATION.md) for a guide on the changes and deployment options.

## Features

- 📋 View all your TickTick projects and tasks
- ✏️ Create new projects and tasks through natural language
- 🔄 Update existing task details (title, content, dates, priority)
- ✅ Mark tasks as complete
- 🗑️ Delete tasks and projects
- 🔄 Full integration with TickTick's open API
- 🔌 Seamless integration with Claude and other MCP clients
- 🐳 **Docker support for remote deployment**
- 🌐 **SSE transport for multi-client access**

## Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- TickTick account with API access
- TickTick API credentials (Client ID, Client Secret, Access Token)
- (Optional) Docker for remote deployment

## Installation

1. **Clone this repository**:

   ```bash
   git clone https://github.com/jacepark12/ticktick-mcp.git
   cd ticktick-mcp
   ```

2. **Install with uv**:

   ```bash
   # Install uv if you don't have it already
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Create a virtual environment
   uv venv

   # Activate the virtual environment
   # On macOS/Linux:
   source .venv/bin/activate
   # On Windows:
   .venv\Scripts\activate

   # Install the package
   uv pip install -e .
   ```

3. **Authenticate with TickTick**:

   ```bash
   # Run the authentication flow
   uv run -m ticktick_mcp.cli auth
   ```

   This will:

   - Ask for your TickTick Client ID and Client Secret
   - Open a browser window for you to log in to TickTick
   - Automatically save your access tokens to a `.env` file

4. **Test your configuration**:
   ```bash
   uv run test_server.py
   ```
   This will verify that your TickTick credentials are working correctly.

## Authentication with TickTick

This server uses OAuth2 to authenticate with TickTick. The setup process is straightforward:

1. Register your application at the [TickTick Developer Center](https://developer.ticktick.com/manage)

   - Set the redirect URI to `http://localhost:8000/callback`
   - Note your Client ID and Client Secret

2. Run the authentication command:

   ```bash
   uv run -m ticktick_mcp.cli auth
   ```

3. Follow the prompts to enter your Client ID and Client Secret

4. A browser window will open for you to authorize the application with your TickTick account

5. After authorizing, you'll be redirected back to the application, and your access tokens will be automatically saved to the `.env` file

The server handles token refresh automatically, so you won't need to reauthenticate unless you revoke access or delete your `.env` file.

## Authentication with Dida365

[滴答清单 - Dida365](https://dida365.com/home) is China version of TickTick, and the authentication process is similar to TickTick. Follow these steps to set up Dida365 authentication:

1. Register your application at the [Dida365 Developer Center](https://developer.dida365.com/manage)

   - Set the redirect URI to `http://localhost:8000/callback`
   - Note your Client ID and Client Secret

2. Add environment variables to your `.env` file:

   ```env
   TICKTICK_BASE_URL='https://api.dida365.com/open/v1'
   TICKTICK_AUTH_URL='https://dida365.com/oauth/authorize'
   TICKTICK_TOKEN_URL='https://dida365.com/oauth/token'
   ```

3. Follow the same authentication steps as for TickTick

## Usage with Claude for Desktop (Local Mode)

1. Install [Claude for Desktop](https://claude.ai/download)
2. Edit your Claude for Desktop configuration file:

   **macOS**:

   ```bash
   nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

   **Windows**:

   ```bash
   notepad %APPDATA%\Claude\claude_desktop_config.json
   ```

3. Add the TickTick MCP server configuration, using absolute paths:

   ```json
   {
     "mcpServers": {
       "ticktick": {
         "command": "<absolute path to uv>",
         "args": [
           "run",
           "--directory",
           "<absolute path to ticktick-mcp directory>",
           "-m",
           "ticktick_mcp.cli",
           "run"
         ]
       }
     }
   }
   ```

4. Restart Claude for Desktop

Once connected, you'll see the TickTick MCP server tools available in Claude, indicated by the 🔨 (tools) icon.

## Remote Server Deployment (Docker)

For hosting the MCP server on a remote machine or Docker server accessible by multiple AI providers.

> 📖 **For detailed deployment instructions**, including Kubernetes, cloud providers, and security best practices, see [DEPLOYMENT.md](DEPLOYMENT.md).

### Quick Start with Docker

1. **Authenticate with TickTick first** (on your local machine):

   ```bash
   uv run -m ticktick_mcp.cli auth
   ```

   This will create a `.env` file with your credentials.

2. **Build and run with Docker Compose**:

   ```bash
   # Copy your .env file with credentials
   cp .env .env.docker

   # Build and start the container
   docker-compose up -d
   ```

3. **Or build and run manually**:

   ```bash
   # Build the image
   docker build -t ticktick-mcp .

   # Run the container with environment variables
   docker run -d \
     --name ticktick-mcp \
     -p 8080:8080 \
     -e TICKTICK_CLIENT_ID=your_client_id \
     -e TICKTICK_CLIENT_SECRET=your_client_secret \
     -e TICKTICK_ACCESS_TOKEN=your_access_token \
     -e TICKTICK_REFRESH_TOKEN=your_refresh_token \
     ticktick-mcp
   ```

4. **The server will be available at**: `http://your-server:8080/sse`

### Connecting AI Providers to Remote Server

Once deployed, configure your AI provider to connect to the remote MCP server.

#### Claude Desktop Remote Connector (OAuth2)

**Claude's Custom Connector UI now supports OAuth2 client credentials authentication**, which this server provides through a built-in gateway.

##### Setup Steps

1. **Generate OAuth credentials** for your server:

   ```bash
   # Easy way: Use the provided script
   python generate-oauth-credentials.py

   # Or manually:
   # Generate a secure client secret
   python -c "import secrets; print(f'claude:{secrets.token_urlsafe(32)}')"
   # Example output: claude:xyzABC123_randomstring

   # Generate JWT signing key
   python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
   # Example output: dGVzdGluZ3NlY3JldGtleTE...
   ```

2. **Add to your `.env` file**:

   ```env
   # OAuth clients (format: client_id:client_secret)
   MCP_OAUTH_CLIENTS=claude:xyzABC123_randomstring

   # JWT signing key (base64 encoded)
   MCP_OAUTH_SIGNING_KEY=dGVzdGluZ3NlY3JldGtleTE...

   # Token expiry (optional, default: 900 seconds = 15 minutes)
   MCP_TOKEN_EXPIRY=900
   ```

3. **Deploy your server** with OAuth gateway:

   ```bash
   docker-compose up -d --build
   ```

4. **Configure Claude Desktop Custom Connector**:

   In Claude's Custom Connector settings, enter:

   - **Server URL**: `https://ticktick.yourdomain.com/sse`
   - **OAuth Client ID**: `claude` (from your MCP_OAUTH_CLIENTS)
   - **OAuth Client Secret**: `xyzABC123_randomstring` (your generated secret)

5. **Claude will automatically**:
   - Request a bearer token from `/oauth/token`
   - Include the token in all SSE and tool call requests
   - Refresh the token before expiry

##### How It Works

The OAuth gateway (`ticktick_mcp/gateway.py`) provides:

1. **`POST /oauth/token`** - Issues JWT bearer tokens for valid client credentials

   - Validates `client_id` and `client_secret` from `MCP_OAUTH_CLIENTS`
   - Returns signed JWT with configurable expiry
   - Supports both Basic Auth and form body authentication

2. **`GET /sse`** - Protected SSE endpoint

   - Validates bearer token from `Authorization: Bearer <token>` header
   - Proxies authenticated requests to internal FastMCP server
   - Returns 401 for missing/invalid tokens

3. **`POST /messages`** - Protected tool call endpoint
   - Same bearer token validation as SSE endpoint
   - Forwards authenticated tool invocations to FastMCP server

##### Security Features

- **JWT tokens** with HMAC-SHA256 signing prevent tampering
- **Short-lived tokens** (15 min default) limit exposure window
- **Separate client credentials** from your TickTick app credentials
- **No per-tool API keys** - authentication handled at gateway level
- **Multiple clients supported** - comma-separate in `MCP_OAUTH_CLIENTS`

##### Architecture

```
Claude Desktop
    |
    | 1. POST /oauth/token (client_id, client_secret)
    v
OAuth Gateway (port 8080)
    |
    | 2. Returns JWT token
    v
Claude Desktop
    |
    | 3. GET /sse (Authorization: Bearer <jwt>)
    v
OAuth Gateway
    |
    | 4. Validates JWT, proxies to FastMCP
    v
FastMCP Server (internal port 8000)
    |
    v
TickTick API
```

##### Legacy OIDC Gateway (Alternative)

For browser-based interactive auth (not recommended for Claude remote connectors):

```yaml
# docker-compose.yml includes oauth2-proxy service
# Configure with your identity provider (Auth0, Keycloak, etc.)
```

Claude cannot follow browser redirects during connector setup, so OAuth2 client credentials (above) is the recommended approach.

### Quick Validation Steps

1. **Start the OAuth-enabled stack**:

   ```bash
   docker-compose up -d --build
   ```

2. **Test OAuth token endpoint**:

   ```bash
   # Request a token using your client credentials
   curl -X POST https://ticktick.yourdomain.com/oauth/token \
     -H "Content-Type: application/json" \
     -d '{
       "grant_type": "client_credentials",
       "client_id": "claude",
       "client_secret": "your_secret_here"
     }'

   # Should return:
   # {
   #   "access_token": "eyJ...",
   #   "token_type": "Bearer",
   #   "expires_in": 900,
   #   "scope": "mcp:full"
   # }
   ```

3. **Test SSE endpoint with bearer token**:

   ```bash
   # Extract token from above response
   TOKEN="eyJ..."

   # Connect to SSE endpoint
   curl -N -H "Authorization: Bearer $TOKEN" \
     https://ticktick.yourdomain.com/sse

   # Should stream MCP protocol JSON events
   ```

4. **Check health endpoint**:

   ```bash
   curl https://ticktick.yourdomain.com/health

   # Should return:
   # {
   #   "status": "healthy",
   #   "gateway": "ticktick-mcp-oauth",
   #   "clients_configured": 1,
   #   "token_expiry_seconds": 900
   # }
   ```

**Troubleshooting**:

- If token endpoint returns 401: Check `MCP_OAUTH_CLIENTS` format in `.env`
- If SSE returns 401: Token may be expired or invalid - request a new one
- If SSE returns 502: FastMCP server not running - check `docker logs ticktick-mcp-server`
- If health check shows 0 clients: `MCP_OAUTH_CLIENTS` not configured properly

#### Other AI Providers

Most MCP-compatible AI providers support SSE transport. Configure them with:

- **URL**: `http://your-server:8080/sse`
- **Transport**: SSE (Server-Sent Events)

### Running Locally without Docker

You can also run the server in remote mode locally:

```bash
# Quick start with provided script
./start-remote.sh

# Or manually with custom options
uv run -m ticktick_mcp.cli run --transport sse --host 0.0.0.0 --port 8080
```

The server will be available at `http://localhost:8080/sse`

### Testing the Server

To verify the SSE server is working:

```bash
# Test connection to local server
python test_sse_server.py

# Test connection to remote server
python test_sse_server.py --host your-server.com --port 8080
```

### Security Considerations

⚠️ **Important**: When deploying to a remote server:

1. **Use HTTPS**: Deploy behind a reverse proxy (nginx, Caddy) with SSL/TLS
2. **Restrict Access**: Use firewall rules to limit who can access the server
3. **Authentication**: Consider adding authentication middleware
4. **Environment Variables**: Never commit `.env` files with credentials
5. **Token Rotation**: Regularly refresh your TickTick access tokens

Example nginx configuration with SSL:

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /sse {
        proxy_pass http://localhost:8080/sse;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
}
```

## Available MCP Tools

| Tool                | Description                          | Parameters                                                                                                                               |
| ------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `get_projects`      | List all your TickTick projects      | None                                                                                                                                     |
| `get_project`       | Get details about a specific project | `project_id`                                                                                                                             |
| `get_project_tasks` | List all tasks in a project          | `project_id`                                                                                                                             |
| `get_task`          | Get details about a specific task    | `project_id`, `task_id`                                                                                                                  |
| `create_task`       | Create a new task                    | `title`, `project_id`, `content` (optional), `start_date` (optional), `due_date` (optional), `priority` (optional)                       |
| `update_task`       | Update an existing task              | `task_id`, `project_id`, `title` (optional), `content` (optional), `start_date` (optional), `due_date` (optional), `priority` (optional) |
| `complete_task`     | Mark a task as complete              | `project_id`, `task_id`                                                                                                                  |
| `delete_task`       | Delete a task                        | `project_id`, `task_id`                                                                                                                  |
| `create_project`    | Create a new project                 | `name`, `color` (optional), `view_mode` (optional)                                                                                       |
| `delete_project`    | Delete a project                     | `project_id`                                                                                                                             |

## Task-specific MCP Tools

### Task Retrieval & Search

| Tool                    | Description                                 | Parameters                                          |
| ----------------------- | ------------------------------------------- | --------------------------------------------------- |
| `get_all_tasks`         | Get all tasks from all projects             | None                                                |
| `get_tasks_by_priority` | Get tasks filtered by priority level        | `priority_id` (0: None, 1: Low, 3: Medium, 5: High) |
| `search_tasks`          | Search tasks by title, content, or subtasks | `search_term`                                       |

### Date-Based Task Retrieval

| Tool                      | Description                          | Parameters                             |
| ------------------------- | ------------------------------------ | -------------------------------------- |
| `get_tasks_due_today`     | Get all tasks due today              | None                                   |
| `get_tasks_due_tomorrow`  | Get all tasks due tomorrow           | None                                   |
| `get_tasks_due_in_days`   | Get tasks due in exactly X days      | `days` (0 = today, 1 = tomorrow, etc.) |
| `get_tasks_due_this_week` | Get tasks due within the next 7 days | None                                   |
| `get_overdue_tasks`       | Get all overdue tasks                | None                                   |

### Getting Things Done (GTD) Framework

| Tool                 | Description                                        | Parameters                          |
| -------------------- | -------------------------------------------------- | ----------------------------------- |
| `get_engaged_tasks`  | Get "engaged" tasks (high priority or overdue)     | None                                |
| `get_next_tasks`     | Get "next" tasks (medium priority or due tomorrow) | None                                |
| `batch_create_tasks` | Create multiple tasks at once                      | `tasks` (list of task dictionaries) |

## Example Prompts for Claude

Here are some example prompts to use with Claude after connecting the TickTick MCP server:

### General

- "Show me all my TickTick projects"
- "Create a new task called 'Finish MCP server documentation' in my work project with high priority"
- "List all tasks in my personal project"
- "Mark the task 'Buy groceries' as complete"
- "Create a new project called 'Vacation Planning' with a blue color"
- "When is my next deadline in TickTick?"

### Task Filtering Queries

- "What tasks do I have due today?"
- "Show me everything that's overdue"
- "Show me all tasks due this week"
- "Search for tasks about 'project alpha'"
- "Show me all tasks with 'client' in the title or description"
- "Show me all my high priority tasks"

### GTD Workflow

Following David Allen's "Getting Things Done" framework, manage an Engaged and Next actions.

- Engaged will retrieve tasks of high priority, due today or overdue.
- Next will retrieve medium priority or due tomorrow.
- Break down complex actions into smaller actions with batch_creation

For example:

- "Time block the rest of my day from 2-8pm with items from my engaged list"
- "Walk me through my next actions and help my identify what I should focus on tomorrow?"
- "Break down this project into 5 smaller actionable tasks"

## Development

### Project Structure

```
ticktick-mcp/
├── .env.template          # Template for environment variables
├── README.md              # Project documentation
├── requirements.txt       # Project dependencies
├── setup.py               # Package setup file
├── test_server.py         # Test script for server configuration
└── ticktick_mcp/          # Main package
    ├── __init__.py        # Package initialization
    ├── authenticate.py    # OAuth authentication utility
    ├── cli.py             # Command-line interface
    └── src/               # Source code
        ├── __init__.py    # Module initialization
        ├── auth.py        # OAuth authentication implementation
        ├── server.py      # MCP server implementation
        └── ticktick_client.py  # TickTick API client
```

### Authentication Flow

The project implements a complete OAuth 2.0 flow for TickTick:

1. **Initial Setup**: User provides their TickTick API Client ID and Secret
2. **Browser Authorization**: User is redirected to TickTick to grant access
3. **Token Reception**: A local server receives the OAuth callback with the authorization code
4. **Token Exchange**: The code is exchanged for access and refresh tokens
5. **Token Storage**: Tokens are securely stored in the local `.env` file
6. **Token Refresh**: The client automatically refreshes the access token when it expires

This simplifies the user experience by handling the entire OAuth flow programmatically.

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
