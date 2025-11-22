#!/usr/bin/env python3
"""
Generate OAuth2 credentials for TickTick MCP Gateway.

This script generates:
1. A secure client ID and secret pair
2. A JWT signing key

Add these to your .env file to enable OAuth authentication.
"""

import base64
import secrets

def generate_client_credentials(client_id="claude"):
    """Generate a client ID and secret pair."""
    client_secret = secrets.token_urlsafe(32)
    return f"{client_id}:{client_secret}"

def generate_signing_key():
    """Generate a base64-encoded JWT signing key."""
    return base64.b64encode(secrets.token_bytes(32)).decode()

def main():
    print("=" * 60)
    print("TickTick MCP OAuth2 Credential Generator")
    print("=" * 60)
    print()
    
    # Generate credentials
    client_credentials = generate_client_credentials()
    signing_key = generate_signing_key()
    
    client_id, client_secret = client_credentials.split(":", 1)
    
    print("✅ Generated OAuth2 Credentials")
    print()
    print("Add these to your .env file:")
    print("-" * 60)
    print(f"MCP_OAUTH_CLIENTS={client_credentials}")
    print(f"MCP_OAUTH_SIGNING_KEY={signing_key}")
    print("-" * 60)
    print()
    print("For Claude Desktop Custom Connector, use:")
    print("-" * 60)
    print(f"OAuth Client ID:     {client_id}")
    print(f"OAuth Client Secret: {client_secret}")
    print("-" * 60)
    print()
    print("⚠️  Security Notes:")
    print("   • Keep these credentials secret")
    print("   • Never commit them to version control")
    print("   • Rotate regularly (monthly recommended)")
    print("   • Use different credentials for each environment")
    print()
    print("💡 To add multiple clients, use comma-separated format:")
    print(f"   MCP_OAUTH_CLIENTS={client_credentials},client2:another_secret")
    print()

if __name__ == "__main__":
    main()
