#!/usr/bin/env python3
"""Start the simple AI provenance tracking system."""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from simple_provenance_tracker.kg_watcher import KnowledgeGraphWatcher


async def main():
    """Start the simple provenance tracking system."""
    print("🚀 Starting Simple AI Provenance Tracker")
    print("=" * 50)
    print("✅ MCP Server: Available via 'python -m simple_provenance_tracker.mcp_server'")
    print("🔍 Knowledge Graph Watcher: Starting...")
    print("📊 Database: Reusing existing ai_commit.ai_commit_executions table")
    print("=" * 50)
    
    # Create and start the knowledge graph watcher
    watcher = KnowledgeGraphWatcher(poll_interval=10)
    
    try:
        print("\n🔍 Knowledge Graph Watcher is now monitoring for AI conversations...")
        print("   - Polls every 10 seconds")
        print("   - Auto-tracks conversations to PostgreSQL")
        print("   - Use Ctrl+C to stop")
        print("\n📝 To enhance commits with provenance:")
        print("   1. Configure Claude Code MCP server:")
        print('      "simple-ai-provenance": {')
        print('        "command": "python",')
        print('        "args": ["-m", "simple_provenance_tracker.mcp_server"]')
        print('      }')
        print("   2. Call enhance_commit_with_provenance before committing")
        print("\n" + "=" * 50)
        
        await watcher.start_watching()
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Shutting down Simple AI Provenance Tracker...")
        watcher.stop_watching()
        print("✅ Stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())