"""
OAuth2 Client Credentials Gateway for TickTick MCP Server.

This gateway sits in front of the FastMCP SSE server and provides:
1. POST /oauth/token - Issues JWT bearer tokens for valid client credentials
2. GET /sse - Proxies to FastMCP SSE server with bearer token validation
3. POST /messages - Proxies tool calls with bearer token validation

Environment Variables:
- MCP_OAUTH_CLIENTS: Comma-separated list of id:secret pairs (e.g., "client1:secret1,client2:secret2")
- MCP_OAUTH_SIGNING_KEY: Base64-encoded secret key for JWT signing (32+ bytes recommended)
- MCP_TOKEN_EXPIRY: Token expiry in seconds (default: 900 = 15 minutes)
"""

import base64
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import httpx

# OAuth2 token request model
class TokenRequest(BaseModel):
    grant_type: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

# Load configuration from environment
OAUTH_CLIENTS = {}
oauth_clients_str = os.getenv("MCP_OAUTH_CLIENTS", "")
if oauth_clients_str:
    for pair in oauth_clients_str.split(","):
        if ":" in pair:
            client_id, client_secret = pair.strip().split(":", 1)
            OAUTH_CLIENTS[client_id] = client_secret

# Signing key for JWT tokens
SIGNING_KEY_B64 = os.getenv("MCP_OAUTH_SIGNING_KEY", "")
if not SIGNING_KEY_B64:
    # Generate a random key if none provided (WARNING: tokens won't survive restart)
    print("WARNING: MCP_OAUTH_SIGNING_KEY not set, generating random key (tokens won't persist across restarts)")
    SIGNING_KEY = base64.b64encode(secrets.token_bytes(32)).decode()
else:
    SIGNING_KEY = SIGNING_KEY_B64

TOKEN_EXPIRY_SECONDS = int(os.getenv("MCP_TOKEN_EXPIRY", "900"))  # 15 minutes default

# FastMCP SSE server URL (internal)
FASTMCP_SERVER_URL = os.getenv("FASTMCP_SERVER_URL", "http://127.0.0.1:8000")

app = FastAPI(
    title="TickTick MCP OAuth Gateway",
    description="OAuth2 client credentials gateway for TickTick MCP server",
    version="1.0.0"
)

security = HTTPBasic()


def validate_client_credentials(client_id: str, client_secret: str) -> bool:
    """Validate client credentials against configured clients."""
    return OAUTH_CLIENTS.get(client_id) == client_secret


def create_access_token(client_id: str) -> str:
    """Create a JWT access token for the given client."""
    now = datetime.utcnow()
    payload = {
        "sub": client_id,
        "iat": now,
        "exp": now + timedelta(seconds=TOKEN_EXPIRY_SECONDS),
        "scope": "mcp:full",
        "iss": "ticktick-mcp-gateway"
    }
    return jwt.encode(payload, SIGNING_KEY, algorithm="HS256")


def verify_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """
    Verify Bearer token from Authorization header.
    Returns client_id (sub claim) if valid, None otherwise.
    """
    if not authorization:
        return None
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    
    token = parts[1]
    try:
        payload = jwt.decode(token, SIGNING_KEY, algorithms=["HS256"])
        # Check expiry (jwt.decode already does this, but explicit check)
        exp = payload.get("exp")
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            return None
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None


@app.post("/oauth/token")
async def token_endpoint(
    request: Request,
    token_request: Optional[TokenRequest] = None
):
    """
    OAuth2 client credentials token endpoint.
    Supports both:
    1. Basic Auth header (preferred)
    2. Form body with client_id and client_secret
    """
    client_id = None
    client_secret = None
    
    # Try Basic Auth first
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            encoded = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            client_id, client_secret = decoded.split(":", 1)
        except Exception:
            pass
    
    # Fall back to form body
    if not client_id and token_request:
        client_id = token_request.client_id
        client_secret = token_request.client_secret
    
    # Validate grant type
    grant_type = token_request.grant_type if token_request else None
    if grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported_grant_type",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Validate credentials
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not validate_client_credentials(client_id, client_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Issue token
    access_token = create_access_token(client_id)
    
    return JSONResponse({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": TOKEN_EXPIRY_SECONDS,
        "scope": "mcp:full"
    })


@app.api_route("/sse", methods=["GET", "POST"])
async def sse_proxy(request: Request):
    """
    Proxy SSE endpoint with bearer token validation.
    Forwards authenticated requests to the FastMCP SSE server.
    Supports both GET (SSE streaming) and POST (MCP messages).
    """
    # Verify bearer token
    authorization = request.headers.get("authorization")
    client_id = verify_bearer_token(authorization)
    
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Forward to FastMCP SSE server
    async with httpx.AsyncClient() as client:
        try:
            # Handle POST requests (MCP messages)
            if request.method == "POST":
                body = await request.body()
                response = await client.post(
                    f"{FASTMCP_SERVER_URL}/sse",
                    content=body,
                    headers={
                        "Content-Type": request.headers.get("content-type", "application/json")
                    },
                    timeout=30.0
                )
                
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
            
            # Handle GET requests (SSE streaming)
            # Stream the SSE response
            async with client.stream(
                "GET",
                f"{FASTMCP_SERVER_URL}/sse",
                headers={
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache"
                },
                timeout=None
            ) as response:
                # Return streaming response
                return StreamingResponse(
                    response.aiter_raw(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no"
                    }
                )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to MCP server: {str(e)}"
            )


@app.post("/messages")
async def messages_proxy(request: Request):
    """
    Proxy tool call endpoint with bearer token validation.
    Forwards authenticated requests to the FastMCP server.
    """
    # Verify bearer token
    authorization = request.headers.get("authorization")
    client_id = verify_bearer_token(authorization)
    
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Forward to FastMCP server
    body = await request.body()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{FASTMCP_SERVER_URL}/messages",
                content=body,
                headers={
                    "Content-Type": request.headers.get("content-type", "application/json")
                },
                timeout=30.0
            )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to MCP server: {str(e)}"
            )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "gateway": "ticktick-mcp-oauth",
        "clients_configured": len(OAUTH_CLIENTS),
        "token_expiry_seconds": TOKEN_EXPIRY_SECONDS
    }


@app.get("/.well-known/mcp.json")
async def mcp_metadata():
    """MCP server metadata endpoint."""
    return {
        "name": "TickTick MCP Server",
        "version": "1.0.0",
        "authentication": {
            "type": "oauth2-client-credentials",
            "token_url": "/oauth/token"
        },
        "transport": "sse",
        "endpoints": {
            "sse": "/sse",
            "messages": "/messages"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    if not OAUTH_CLIENTS:
        print("ERROR: No OAuth clients configured. Set MCP_OAUTH_CLIENTS environment variable.")
        print("Example: MCP_OAUTH_CLIENTS=client1:secret1,client2:secret2")
        exit(1)
    
    print(f"Starting OAuth gateway with {len(OAUTH_CLIENTS)} configured client(s)")
    print(f"Token expiry: {TOKEN_EXPIRY_SECONDS} seconds")
    print(f"FastMCP server URL: {FASTMCP_SERVER_URL}")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
