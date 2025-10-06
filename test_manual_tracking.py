#!/usr/bin/env python3
"""Test manual conversation tracking without database dependencies."""

import asyncio
import json

# Test our current conversation via knowledge graph
async def test_current_conversation():
    """Test by storing this current conversation in knowledge graph."""
    print("🧪 Testing Manual Conversation Tracking")
    print("=" * 50)
    
    # Simulate the current conversation
    current_prompt = "Ok. Let us test it now to see if this prompts are stored or not"
    current_response = """Perfect! Let's test the system to see if prompts are being captured and stored. I'll help you test it step by step.

I'll create a todo list to track our testing progress and then start testing the components one by one."""
    
    print("📝 Current Conversation:")
    print(f"Prompt: {current_prompt}")
    print(f"Response: {current_response[:100]}...")
    print()
    
    # Try to store this in knowledge graph
    try:
        # Store conversation in knowledge graph
        from mcp__knowledge_graph__aim_create_entities import mcp__knowledge_graph__aim_create_entities
        
        result = await mcp__knowledge_graph__aim_create_entities({
            "entities": [
                {
                    "name": f"TestConversation_{int(asyncio.get_event_loop().time())}",
                    "entityType": "ai_interaction", 
                    "observations": [
                        f"User: {current_prompt}",
                        f"Assistant: {current_response}",
                        "Context: Testing the simple AI provenance tracking system"
                    ]
                }
            ]
        })
        
        print("✅ Successfully stored conversation in knowledge graph:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"❌ Failed to store in knowledge graph: {e}")
        print("This is expected if knowledge graph MCP is not available")
    
    print("\n" + "=" * 50)
    print("🔍 Next: Check if knowledge graph watcher detects this conversation")


if __name__ == "__main__":
    asyncio.run(test_current_conversation())