"""
OAuth2 Authorization Code Flow Gateway for Claude.ai Custom Connectors.

This gateway implements:
1. Authorization endpoint for browser-based OAuth flow
2. Token endpoint for exchanging authorization codes
3. Token refresh
4. SSE/messages proxying with Bearer token validation
"""

import base64
import os
import secrets
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from urllib.parse import urlencode, parse_qs

import jwt
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse, HTMLResponse
from html import escape
from pydantic import BaseModel
import httpx

# In-memory stores (use Redis or DB in production)
authorization_codes: Dict[str, dict] = {}
access_tokens: Dict[str, dict] = {}
refresh_tokens: Dict[str, dict] = {}

# OAuth2 models
class TokenRequest(BaseModel):
    grant_type: str
    code: Optional[str] = None
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    code_verifier: Optional[str] = None

# Load configuration
OAUTH_CLIENTS = {}
oauth_clients_str = os.getenv("MCP_OAUTH_CLIENTS", "")
if oauth_clients_str:
    for pair in oauth_clients_str.split(","):
        if ":" in pair:
            client_id, client_secret = pair.strip().split(":", 1)
            OAUTH_CLIENTS[client_id] = client_secret

SIGNING_KEY_B64 = os.getenv("MCP_OAUTH_SIGNING_KEY", "")
if not SIGNING_KEY_B64:
    print("WARNING: MCP_OAUTH_SIGNING_KEY not set, generating random key")
    SIGNING_KEY = base64.b64encode(secrets.token_bytes(32)).decode()
else:
    SIGNING_KEY = SIGNING_KEY_B64

TOKEN_EXPIRY_SECONDS = int(os.getenv("MCP_TOKEN_EXPIRY", "3600"))  # 1 hour
REFRESH_TOKEN_EXPIRY_SECONDS = int(os.getenv("MCP_REFRESH_TOKEN_EXPIRY", "2592000"))  # 30 days
FASTMCP_SERVER_URL = os.getenv("FASTMCP_SERVER_URL", "http://127.0.0.1:8000")

# Claude.ai callback URL
CLAUDE_CALLBACK_URL = "https://claude.ai/api/mcp/auth_callback"

app = FastAPI(
    title="TickTick MCP OAuth Authorization Gateway",
    description="OAuth2 Authorization Code flow for Claude.ai",
    version="2.0.0"
)

# Logging setup
LOG_LEVEL = os.getenv("MCP_OAUTH_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("oauth_gateway")
DISABLE_PKCE = os.getenv("MCP_OAUTH_DISABLE_PKCE", "0") in ("1", "true", "TRUE")


def _get_request_origin(request: Request) -> str:
    """Best-effort scheme/host reconstruction behind proxies."""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if not host:
        host = request.url.netloc
    return f"{proto}://{host}".rstrip("/")
@app.get("/")
async def root_metadata():
    """Human-friendly landing page for discovery checks."""
    return {
        "message": "TickTick MCP OAuth gateway is running",
        "discovery": {
            "mcp": "/.well-known/mcp.json",
            "oauth_authorization_server": "/.well-known/oauth-authorization-server",
            "oauth_protected_resource": "/.well-known/oauth-protected-resource"
        }
    }


@app.post("/")
async def root_post_probe():
    """Handle generic POST probes from clients expecting JSON."""
    return {
        "message": "Use /messages for MCP requests and /oauth/token for OAuth flows"
    }



def create_access_token(user_id: str) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(seconds=TOKEN_EXPIRY_SECONDS),
        "scope": "mcp:full",
        "iss": "ticktick-mcp-gateway"
    }
    return jwt.encode(payload, SIGNING_KEY, algorithm="HS256")


def verify_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Verify Bearer token from Authorization header."""
    if not authorization:
        logger.warning("verify_bearer_token: missing Authorization header")
        return None
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning("verify_bearer_token: malformed Authorization header")
        return None
    
    token = parts[1]
    token_prefix = token[:8]
    logger.debug("verify_bearer_token: received token prefix %s", token_prefix)
    
    # Check in-memory store first
    if token in access_tokens:
        token_data = access_tokens[token]
        if token_data["expires_at"] > datetime.now(timezone.utc):
            return token_data["user_id"]
        else:
            # Token expired
            del access_tokens[token]
            logger.warning("verify_bearer_token: token prefix %s expired", token_prefix)
            return None
    
    # Fall back to JWT validation
    try:
        payload = jwt.decode(token, SIGNING_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.InvalidTokenError:
        logger.warning("verify_bearer_token: token prefix %s failed JWT validation", token_prefix)
        return None


@app.get("/authorize")
async def authorize(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: Optional[str] = None,
    code_challenge: Optional[str] = None,
    code_challenge_method: Optional[str] = None
):
    """
    OAuth2 authorization endpoint.
    For demo purposes, this automatically approves and redirects.
    In production, this would show a consent screen.
    """
    # Validate parameters
    if response_type != "code":
        return JSONResponse(
            {"error": "unsupported_response_type"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # For Claude.ai, validate redirect_uri
    if redirect_uri != CLAUDE_CALLBACK_URL:
        return JSONResponse(
            {"error": "invalid_redirect_uri", "detail": f"Expected {CLAUDE_CALLBACK_URL}"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Generate authorization code
    auth_code = secrets.token_urlsafe(32)
    
    # Store authorization code with associated data
    authorization_codes[auth_code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope or "mcp:full",
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "user_id": f"user_{uuid.uuid4().hex[:8]}"  # Demo user ID
    }
    
    # Redirect back to Claude with authorization code
    params = {
        "code": auth_code,
        "state": state
    }
    
    redirect_url = f"{redirect_uri}?{urlencode(params)}"
    safe_redirect_url = escape(redirect_url, quote=True)
    # Provide both auto-redirect and manual link to satisfy browser or app-specific flows.
    html = f"""
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\">
        <meta http-equiv=\"refresh\" content=\"0;url={safe_redirect_url}\">
        <title>Redirecting...</title>
        <style>
            body {{ font-family: system-ui, sans-serif; text-align: center; padding-top: 4rem; color: #0f172a; }}
            a {{ color: #2563eb; text-decoration: none; font-size: 1.1rem; }}
        </style>
    </head>
    <body>
        <p>Completing TickTick MCP authorization...</p>
        <p>If you are not redirected automatically, <a href=\"{safe_redirect_url}\">click here to continue</a>.</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)


@app.post("/oauth/token")
async def token_endpoint(request: Request):
    """Unified OAuth2 token endpoint supporting JSON and form-encoded bodies with detailed logging."""
    content_type = request.headers.get("content-type", "")
    data: Dict[str, str] = {}

    if "application/x-www-form-urlencoded" in content_type:
        body = (await request.body()).decode()
        import urllib.parse
        parsed = urllib.parse.parse_qs(body)
        # parse_qs always returns list values; flatten to first item or empty string
        data = {k: (v[0] if v else "") for k, v in parsed.items()}
    else:
        try:
            data = await request.json()
        except Exception:
            data = {}

    grant_type = data.get("grant_type")
    logger.info(f"/oauth/token grant_type={grant_type}")
    if not grant_type:
        return JSONResponse({"error": "invalid_request", "detail": "missing_grant_type"}, status_code=400)

    if grant_type == "authorization_code":
        code = data.get("code")
        redirect_uri = data.get("redirect_uri")
        code_verifier = data.get("code_verifier")
        logger.info(f"authorization_code flow code_present={'yes' if code else 'no'} redirect_uri={redirect_uri}")

        if not code or code not in authorization_codes:
            logger.warning("authorization_code not found or missing")
            return JSONResponse({"error": "invalid_grant", "reason": "code_not_found"}, status_code=400)

        auth_data = authorization_codes[code]
        logger.info(f"auth_data stored redirect_uri={auth_data['redirect_uri']} expires_at={auth_data['expires_at'].isoformat()} scope={auth_data['scope']} pkce={'yes' if auth_data.get('code_challenge') else 'no'}")

        if redirect_uri and redirect_uri != auth_data["redirect_uri"]:
            logger.warning("redirect_uri mismatch")
            return JSONResponse({"error": "invalid_grant", "reason": "redirect_uri_mismatch"}, status_code=400)

        now = datetime.now(timezone.utc)
        if auth_data["expires_at"] < now:
            del authorization_codes[code]
            logger.warning("authorization_code expired")
            return JSONResponse({"error": "invalid_grant", "reason": "code_expired"}, status_code=400)

        # PKCE verification
        if auth_data.get("code_challenge") and not DISABLE_PKCE:
            if not code_verifier:
                logger.warning("code_verifier missing while PKCE required")
                return JSONResponse({"error": "invalid_grant", "reason": "code_verifier_required"}, status_code=400)
            import hashlib
            sha = hashlib.sha256(code_verifier.encode()).digest()
            padded = base64.urlsafe_b64encode(sha).decode()
            unpadded = padded.rstrip("=")
            stored = auth_data["code_challenge"]
            pkce_match = stored in (padded, unpadded)
            logger.info(f"PKCE verify stored={stored} computed_unpadded={unpadded} computed_padded={padded} match={pkce_match}")
            if not pkce_match:
                return JSONResponse({"error": "invalid_grant", "reason": "pkce_mismatch"}, status_code=400)
        elif auth_data.get("code_challenge") and DISABLE_PKCE:
            logger.info("PKCE disabled via env MCP_OAUTH_DISABLE_PKCE; skipping verification")

        user_id = auth_data["user_id"]
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        access_tokens[access_token] = {
            "user_id": user_id,
            "scope": auth_data["scope"],
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=TOKEN_EXPIRY_SECONDS)
        }
        refresh_tokens[refresh_token] = {
            "user_id": user_id,
            "scope": auth_data["scope"],
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=REFRESH_TOKEN_EXPIRY_SECONDS)
        }

        del authorization_codes[code]
        logger.info("authorization_code exchanged successfully; tokens issued")

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": TOKEN_EXPIRY_SECONDS,
            "refresh_token": refresh_token,
            "scope": auth_data["scope"]
        })

    elif grant_type == "refresh_token":
        refresh_token = data.get("refresh_token")
        logger.info("refresh_token flow started")
        if not refresh_token or refresh_token not in refresh_tokens:
            logger.warning("refresh_token not found")
            return JSONResponse({"error": "invalid_grant", "reason": "refresh_token_not_found"}, status_code=400)

        refresh_data = refresh_tokens[refresh_token]
        if refresh_data["expires_at"] < datetime.now(timezone.utc):
            del refresh_tokens[refresh_token]
            logger.warning("refresh_token expired")
            return JSONResponse({"error": "invalid_grant", "reason": "refresh_token_expired"}, status_code=400)

        access_token = secrets.token_urlsafe(32)
        access_tokens[access_token] = {
            "user_id": refresh_data["user_id"],
            "scope": refresh_data["scope"],
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=TOKEN_EXPIRY_SECONDS)
        }
        logger.info("refresh_token accepted; new access_token issued")

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": TOKEN_EXPIRY_SECONDS,
            "scope": refresh_data["scope"]
        })

    else:
        logger.warning(f"unsupported grant_type {grant_type}")
        return JSONResponse({"error": "unsupported_grant_type", "detail": grant_type}, status_code=400)


@app.api_route("/sse", methods=["GET", "POST"])
async def sse_proxy(request: Request):
    """Proxy SSE endpoint with bearer token validation."""
    authorization = request.headers.get("authorization")
    user_id = verify_bearer_token(authorization)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    async with httpx.AsyncClient() as client:
        try:
            if request.method == "POST":
                body = await request.body()
                response = await client.post(
                    f"{FASTMCP_SERVER_URL}/sse",
                    content=body,
                    headers={"Content-Type": request.headers.get("content-type", "application/json")},
                    timeout=30.0
                )
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
            
            # GET request - SSE streaming
            async with client.stream(
                "GET",
                f"{FASTMCP_SERVER_URL}/sse",
                headers={
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache"
                },
                timeout=None
            ) as response:
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
    """Proxy messages endpoint with bearer token validation."""
    authorization = request.headers.get("authorization")
    user_id = verify_bearer_token(authorization)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    body = await request.body()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{FASTMCP_SERVER_URL}/messages",
                content=body,
                headers={"Content-Type": request.headers.get("content-type", "application/json")},
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
        "gateway": "ticktick-mcp-oauth-authz",
        "auth_type": "authorization_code",
        "token_expiry_seconds": TOKEN_EXPIRY_SECONDS,
        "active_tokens": len(access_tokens)
    }


@app.get("/.well-known/mcp.json")
async def mcp_metadata(request: Request):
    """MCP server metadata endpoint."""
    origin = _get_request_origin(request)
    return {
        "name": "TickTick MCP Server",
        "version": "2.0.0",
        "authentication": {
            "type": "oauth2-authorization-code",
            "authorization_url": f"{origin}/authorize",
            "token_url": f"{origin}/oauth/token",
            "scopes": ["mcp:full", "claudeai"],
            "pkce": True
        },
        "transport": "sse",
        "endpoints": {
            "sse": f"{origin}/sse",
            "messages": f"{origin}/messages"
        }
    }


@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata(request: Request):
    """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
    origin = _get_request_origin(request)
    return {
        "issuer": origin,
        "authorization_endpoint": f"{origin}/authorize",
        "token_endpoint": f"{origin}/oauth/token",
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["mcp:full", "claudeai"],
        "token_endpoint_auth_methods_supported": ["none"],
    }


@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata(request: Request):
    """Basic protected resource metadata for Claude discovery."""
    origin = _get_request_origin(request)
    auth_metadata = f"{origin}/.well-known/oauth-authorization-server"
    return {
        "issuer": origin,
        "resource": "ticktick-mcp",
        "authorization_servers": [auth_metadata],
        "endpoints": {
            "sse": f"{origin}/sse",
            "messages": f"{origin}/messages"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    print(f"Starting OAuth Authorization Code gateway")
    print(f"Token expiry: {TOKEN_EXPIRY_SECONDS} seconds")
    print(f"FastMCP server URL: {FASTMCP_SERVER_URL}")
    print(f"Claude callback URL: {CLAUDE_CALLBACK_URL}")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
