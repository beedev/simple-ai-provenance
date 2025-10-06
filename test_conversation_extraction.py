#!/usr/bin/env python3
"""Test conversation extraction from knowledge graph entities."""

import sys
sys.path.append('src')

from simple_provenance_tracker.kg_watcher import KnowledgeGraphWatcher


def test_conversation_extraction():
    """Test the conversation extraction logic."""
    print("🧪 Testing Conversation Extraction Logic")
    print("=" * 50)
    
    # Create watcher
    watcher = KnowledgeGraphWatcher()
    
    # Test entity 1: TestingPromptCapture
    entity1 = {
        "name": "TestingPromptCapture",
        "entityType": "ai_interaction",
        "observations": [
            "User: Ok. Let us test it now to see if this prompts are stored or not",
            "Assistant: Perfect! Let's test the system to see if prompts are being captured and stored. I'll help you test it step by step. I'll create a todo list to track our testing progress and then start testing the components one by one.",
            "Context: Testing the simple AI provenance tracking system to verify prompt capture functionality"
        ]
    }
    
    # Test entity 2: ImplementationDiscussion  
    entity2 = {
        "name": "ImplementationDiscussion",
        "entityType": "ai_interaction",
        "observations": [
            "User: Remove the old code",
            "Assistant: I'll clean up the old complex implementation and keep only the simple, working version. The project is now clean, simple, and actually functional - exactly what you wanted!",
            "Context: Cleaning up old MCP implementation and preparing for testing"
        ]
    }
    
    # Test extraction
    print("🔍 Testing Entity 1:")
    conversation1 = watcher._extract_conversation_from_entity(entity1)
    if conversation1:
        print("✅ Conversation detected:")
        print(f"   Prompt: {conversation1['prompt_text']}")
        print(f"   Response: {conversation1['response_text'][:80]}...")
        print(f"   Context: {conversation1['context']}")
    else:
        print("❌ No conversation detected")
    
    print("\n🔍 Testing Entity 2:")
    conversation2 = watcher._extract_conversation_from_entity(entity2)
    if conversation2:
        print("✅ Conversation detected:")
        print(f"   Prompt: {conversation2['prompt_text']}")
        print(f"   Response: {conversation2['response_text'][:80]}...")
        print(f"   Context: {conversation2['context']}")
    else:
        print("❌ No conversation detected")
    
    print("\n" + "=" * 50)
    print("✅ Conversation extraction test completed!")
    
    return conversation1, conversation2


if __name__ == "__main__":
    test_conversation_extraction()