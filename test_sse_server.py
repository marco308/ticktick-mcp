#!/usr/bin/env python3
"""
Simple test script to verify the SSE server is working.
This script can be run without authentication to test basic server functionality.
"""

import sys
import time
import urllib.request
import urllib.error
from urllib.parse import urljoin

def test_sse_endpoint(host: str = "localhost", port: int = 8080, timeout: int = 5):
    """Test if the SSE endpoint is accessible."""
    url = f"http://{host}:{port}/sse"
    
    print(f"Testing TickTick MCP SSE server at {url}")
    print("-" * 60)
    
    try:
        print(f"Attempting connection (timeout: {timeout}s)...")
        req = urllib.request.Request(url)
        req.add_header('Accept', 'text/event-stream')
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            print(f"✅ Connection successful!")
            print(f"   Status Code: {response.status}")
            print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            
            # Read a small amount to verify SSE stream
            print("\n📡 Reading initial SSE stream data...")
            chunk = response.read(200).decode('utf-8', errors='ignore')
            if chunk:
                print(f"   Received data: {chunk[:100]}...")
            
            return True
            
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"❌ Connection failed: {e.reason}")
        print("\nPossible causes:")
        print("  - Server is not running")
        print("  - Server is running on a different port")
        print("  - Firewall blocking connection")
        return False
    except TimeoutError:
        print(f"❌ Connection timeout after {timeout}s")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test TickTick MCP SSE server connectivity"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Server host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Server port (default: 8080)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Connection timeout in seconds (default: 5)"
    )
    
    args = parser.parse_args()
    
    success = test_sse_endpoint(args.host, args.port, args.timeout)
    
    print("\n" + "=" * 60)
    if success:
        print("✅ SSE server is working correctly!")
        print("\nYou can connect your MCP client to:")
        print(f"   http://{args.host}:{args.port}/sse")
        sys.exit(0)
    else:
        print("❌ SSE server test failed")
        print("\nTroubleshooting:")
        print("  1. Make sure the server is running:")
        print("     ./start-remote.sh")
        print("  2. Check if the port is correct")
        print("  3. Verify your .env file has valid credentials")
        sys.exit(1)

if __name__ == "__main__":
    main()
