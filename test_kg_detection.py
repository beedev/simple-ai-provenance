#!/usr/bin/env python3
"""Test knowledge graph conversation detection."""

import asyncio
import json
import sys
sys.path.append('src')

from simple_provenance_tracker.kg_watcher import KnowledgeGraphWatcher


async def test_kg_detection():
    """Test if knowledge graph watcher can detect our test conversations."""
    print("🔍 Testing Knowledge Graph Conversation Detection")
    print("=" * 50)
    
    # Create a watcher
    watcher = KnowledgeGraphWatcher(poll_interval=1)  # Fast polling for testing
    
    # Override the read method to use real knowledge graph
    async def mock_read_kg():
        """Read actual knowledge graph using MCP."""
        try:
            # Import the MCP function
            from mcp__knowledge_graph__aim_read_graph import mcp__knowledge_graph__aim_read_graph
            result = await mcp__knowledge_graph__aim_read_graph({})
            print(f"📊 Knowledge Graph contains {len(result.get('entities', []))} entities")
            return result
        except Exception as e:
            print(f"❌ Could not read knowledge graph: {e}")
            return {"entities": []}
    
    # Replace the method
    watcher._read_knowledge_graph = mock_read_kg
    
    # Override the track method to not use database
    async def mock_track(conversation):
        print("✅ Would track conversation:")
        print(f"   Prompt: {conversation['prompt_text'][:80]}...")
        print(f"   Response: {conversation['response_text'][:80]}...")
        print(f"   Repo: {conversation['repo_path']}")
        print(f"   Context: {conversation['context']}")
        return True
    
    watcher._track_conversation = mock_track
    
    # Run one check cycle
    print("🔄 Running knowledge graph check...")
    await watcher._check_for_new_conversations()
    
    print("\n" + "=" * 50)
    print("✅ Knowledge graph detection test completed!")


if __name__ == "__main__":
    asyncio.run(test_kg_detection())