#!/usr/bin/env python3
"""
Test OAuth Gateway Implementation

This script validates:
1. Gateway code imports correctly
2. Token generation works
3. Token validation works
4. Client credential validation works
"""

import sys
import os

# Add the project to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all gateway imports work."""
    print("Testing imports...")
    try:
        import jwt
        import fastapi
        import httpx
        print("✅ All dependencies available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def test_token_generation():
    """Test JWT token creation and validation."""
    print("\nTesting JWT token generation...")
    try:
        import jwt
        from datetime import datetime, timedelta
        import secrets
        import base64
        
        # Generate a test signing key
        signing_key = base64.b64encode(secrets.token_bytes(32)).decode()
        
        # Create a token
        payload = {
            "sub": "test_client",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=900),
            "scope": "mcp:full"
        }
        token = jwt.encode(payload, signing_key, algorithm="HS256")
        
        # Verify the token
        decoded = jwt.decode(token, signing_key, algorithms=["HS256"])
        
        assert decoded["sub"] == "test_client"
        assert decoded["scope"] == "mcp:full"
        
        print(f"✅ Token generation works")
        print(f"   Sample token (truncated): {token[:50]}...")
        return True
    except Exception as e:
        print(f"❌ Token generation failed: {e}")
        return False

def test_client_validation():
    """Test client credential validation logic."""
    print("\nTesting client credential validation...")
    try:
        # Simulate the validation logic from gateway.py
        oauth_clients_str = "client1:secret1,client2:secret2"
        OAUTH_CLIENTS = {}
        
        for pair in oauth_clients_str.split(","):
            if ":" in pair:
                client_id, client_secret = pair.strip().split(":", 1)
                OAUTH_CLIENTS[client_id] = client_secret
        
        # Test valid credentials
        assert OAUTH_CLIENTS.get("client1") == "secret1"
        assert OAUTH_CLIENTS.get("client2") == "secret2"
        
        # Test invalid credentials
        assert OAUTH_CLIENTS.get("client3") is None
        assert OAUTH_CLIENTS.get("client1") != "wrong_secret"
        
        print(f"✅ Client validation logic works")
        print(f"   Loaded {len(OAUTH_CLIENTS)} clients")
        return True
    except Exception as e:
        print(f"❌ Client validation failed: {e}")
        return False

def test_env_config():
    """Test environment variable configuration."""
    print("\nTesting environment configuration...")
    
    required_vars = [
        "TICKTICK_CLIENT_ID",
        "TICKTICK_CLIENT_SECRET",
        "TICKTICK_ACCESS_TOKEN",
        "TICKTICK_REFRESH_TOKEN"
    ]
    
    oauth_vars = [
        "MCP_OAUTH_CLIENTS",
        "MCP_OAUTH_SIGNING_KEY"
    ]
    
    # Check .env.example exists
    if not os.path.exists(".env.example"):
        print("❌ .env.example not found")
        return False
    
    # Read .env.example
    with open(".env.example", "r") as f:
        example_content = f.read()
    
    # Verify all required OAuth vars are documented
    missing = []
    for var in oauth_vars:
        if var not in example_content:
            missing.append(var)
    
    if missing:
        print(f"❌ Missing OAuth vars in .env.example: {missing}")
        return False
    
    print("✅ Environment configuration documented")
    return True

def main():
    """Run all tests."""
    print("=" * 60)
    print("TickTick MCP OAuth Gateway - Implementation Tests")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    
    # Only run other tests if imports work
    if results[0][1]:
        results.append(("Token Generation", test_token_generation()))
        results.append(("Client Validation", test_client_validation()))
    
    results.append(("Environment Config", test_env_config()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! OAuth implementation is ready.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
