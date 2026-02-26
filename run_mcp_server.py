#!/usr/bin/env python3
"""MCP Server entry point for simple AI provenance tracking."""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run the MCP server
from simple_provenance_tracker.mcp_server import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())