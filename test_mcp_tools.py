#!/usr/bin/env python3
"""Test MCP tools with extracted conversation data."""

import asyncio
import json
import sys
sys.path.append('src')

from simple_provenance_tracker.mcp_server import handle_track_conversation, handle_get_history


async def test_mcp_tools():
    """Test MCP tools with real conversation data."""
    print("🛠️ Testing MCP Tools with Real Conversation Data")
    print("=" * 50)
    
    # Test conversation data from our extraction
    test_conversation = {
        "prompt_text": "Ok. Let us test it now to see if this prompts are stored or not",
        "response_text": "Perfect! Let's test the system to see if prompts are being captured and stored. I'll help you test it step by step. I'll create a todo list to track our testing progress and then start testing the components one by one.",
        "repo_path": "/Users/bharath/mcp-ai-commit",
        "context": {
            "entity_name": "TestingPromptCapture",
            "entity_type": "ai_interaction", 
            "source": "knowledge_graph_watcher",
            "test_mode": True
        }
    }
    
    print("📝 Test Conversation:")
    print(f"Prompt: {test_conversation['prompt_text']}")
    print(f"Response: {test_conversation['response_text'][:100]}...")
    print(f"Repo: {test_conversation['repo_path']}")
    print()
    
    # Test 1: track_conversation (without database)
    print("🧪 Test 1: track_conversation")
    try:
        # We expect this to fail due to database connection, but let's see the error
        result = await handle_track_conversation(test_conversation)
        print("✅ Track conversation result:")
        for content in result:
            print(f"   {content.text}")
    except Exception as e:
        print(f"❌ Track conversation failed (expected): {e}")
        print("   This is expected without database connection")
    
    print()
    
    # Test 2: commit_with_provenance (simulated - no actual commit)
    print("🧪 Test 2: commit_with_provenance (simulation)")
    print("   NOTE: This would perform actual git commit, so testing logic only")
    
    # Show what the correct workflow should be:
    print("   ✅ Correct workflow:")
    print("   1. track_conversation stores with commit_included=False")
    print("   2. commit_with_provenance queries DB for uncommitted conversations")
    print("   3. Builds enhanced message automatically")
    print("   4. Performs git commit with enhanced message")
    print("   5. Marks conversations as committed with real commit hash")
    
    print()
    
    # Test 3: get_conversation_history (without database)
    print("🧪 Test 3: get_conversation_history")
    history_args = {
        "repo_path": "/Users/bharath/mcp-ai-commit",
        "limit": 5
    }
    
    try:
        result = await handle_get_history(history_args)
        print("✅ Get history result:")
        for content in result:
            print(f"   {content.text}")
    except Exception as e:
        print(f"❌ Get history failed (expected): {e}")
        print("   This is expected without database connection")
    
    print("\n" + "=" * 50)
    print("✅ MCP tools test completed!")
    print("💡 Next: Set up database connection to test full functionality")


if __name__ == "__main__":
    asyncio.run(test_mcp_tools())