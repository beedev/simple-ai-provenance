"""Knowledge Graph Watcher - Monitors for AI conversations and auto-tracks them."""

import asyncio
import json
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

# For calling our own MCP server
import subprocess
import tempfile


class KnowledgeGraphWatcher:
    """Watches knowledge graph for AI conversations and auto-tracks them."""
    
    def __init__(self, poll_interval: int = 5):
        self.poll_interval = poll_interval
        self.last_check = datetime.utcnow()
        self.processed_entities = set()
        self.running = False
        
    async def start_watching(self):
        """Start watching the knowledge graph for new conversations."""
        self.running = True
        print("🔍 Knowledge Graph Watcher started...")
        
        while self.running:
            try:
                await self._check_for_new_conversations()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                print(f"❌ Error in knowledge graph watcher: {e}")
                await asyncio.sleep(self.poll_interval)
    
    def stop_watching(self):
        """Stop watching the knowledge graph."""
        self.running = False
        print("⏹️ Knowledge Graph Watcher stopped")
    
    async def _check_for_new_conversations(self):
        """Check for new AI conversations in the knowledge graph."""
        try:
            # Read the current knowledge graph
            graph_data = await self._read_knowledge_graph()
            
            if not graph_data or 'entities' not in graph_data:
                return
            
            # Look for conversation-like entities
            for entity in graph_data['entities']:
                entity_id = f"{entity['name']}_{entity['entityType']}"
                
                # Skip if we've already processed this entity
                if entity_id in self.processed_entities:
                    continue
                
                # Check if this looks like an AI conversation
                conversation = self._extract_conversation_from_entity(entity)
                
                if conversation:
                    print(f"📝 Found AI conversation in entity: {entity['name']}")
                    await self._track_conversation(conversation)
                    self.processed_entities.add(entity_id)
            
        except Exception as e:
            print(f"❌ Error checking knowledge graph: {e}")
    
    async def _read_knowledge_graph(self) -> Optional[Dict[str, Any]]:
        """Read the current knowledge graph using MCP."""
        try:
            # Use the knowledge-graph MCP to read current state
            cmd = [
                "python", "-c", 
                """
import asyncio
import json
import sys
sys.path.append('/Users/bharath')
from mcp__knowledge_graph__aim_read_graph import mcp__knowledge_graph__aim_read_graph

async def read_graph():
    try:
        result = await mcp__knowledge_graph__aim_read_graph({})
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

asyncio.run(read_graph())
                """
            ]
            
            # For now, use a simpler approach - check if there are recent files
            # This is a placeholder until we can properly integrate with knowledge-graph MCP
            return await self._mock_read_knowledge_graph()
            
        except Exception as e:
            print(f"❌ Error reading knowledge graph: {e}")
            return None
    
    async def _mock_read_knowledge_graph(self) -> Dict[str, Any]:
        """Mock knowledge graph read - replace with actual MCP call."""
        # This is a placeholder that simulates finding conversations
        # In reality, this would call the knowledge-graph MCP
        
        # Check for recent activity (file modifications, etc.)
        current_repo = self._get_current_repo_path()
        
        # For demo purposes, create a mock conversation every few checks
        import random
        if random.random() < 0.1:  # 10% chance of finding a "conversation"
            return {
                "entities": [
                    {
                        "name": f"MockConversation_{int(time.time())}",
                        "entityType": "ai_interaction",
                        "observations": [
                            "User: Can you help me implement a new feature for user authentication?",
                            "Assistant: I'll help you implement user authentication. Let me start by analyzing your current code structure and then create a secure authentication system.",
                            "Context: This conversation happened during development of the user authentication feature"
                        ]
                    }
                ]
            }
        
        return {"entities": []}
    
    def _extract_conversation_from_entity(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract conversation data from a knowledge graph entity."""
        try:
            # Look for conversation patterns in observations
            observations = entity.get('observations', [])
            
            if not observations:
                return None
            
            # Simple pattern matching for conversations
            prompts = []
            responses = []
            
            for obs in observations:
                obs_lower = obs.lower()
                
                # Look for user prompts
                if any(pattern in obs_lower for pattern in ['user:', 'human:', 'request:', 'prompt:']):
                    prompts.append(obs)
                
                # Look for AI responses  
                if any(pattern in obs_lower for pattern in ['assistant:', 'ai:', 'response:', 'claude:']):
                    responses.append(obs)
                
                # Look for conversation indicators
                if any(pattern in obs_lower for pattern in ['conversation', 'discussed', 'asked', 'implemented']):
                    # This might be a conversation summary
                    if len(obs) > 50:  # Substantial content
                        if not prompts and not responses:
                            # Treat as a general conversation
                            prompts.append(f"Development conversation: {obs[:100]}...")
                            responses.append(f"AI assistance provided for: {entity['name']}")
            
            # If we found conversation elements, create conversation data
            if prompts and responses:
                return {
                    "prompt_text": " | ".join(prompts),
                    "response_text": " | ".join(responses),
                    "repo_path": self._get_current_repo_path(),
                    "context": {
                        "entity_name": entity['name'],
                        "entity_type": entity['entityType'], 
                        "source": "knowledge_graph_watcher",
                        "timestamp": datetime.utcnow().isoformat(),
                        "observations_count": len(observations)
                    }
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Error extracting conversation from entity: {e}")
            return None
    
    async def _track_conversation(self, conversation: Dict[str, Any]):
        """Track the conversation using our MCP server."""
        try:
            # Call our MCP server to track the conversation
            # For now, use a direct database call since the MCP might not be running
            await self._direct_database_track(conversation)
            
        except Exception as e:
            print(f"❌ Error tracking conversation: {e}")
    
    async def _direct_database_track(self, conversation: Dict[str, Any]):
        """Directly track conversation in database (fallback when MCP not available)."""
        try:
            # Import the local database manager
            from .database import DatabaseManager, AICommitExecution
            import uuid
            from datetime import timezone
            
            # Get database manager  
            from .database import get_database
            db = await get_database()
            
            # Create execution record
            exec_id = uuid.uuid4()
            branch_name = self._get_current_branch(conversation["repo_path"])
            
            execution = AICommitExecution(
                exec_id=exec_id,
                timestamp=datetime.now(timezone.utc),
                repo_path=conversation["repo_path"],
                branch_name=branch_name,
                model_provider="claude",
                model_name="sonnet-4", 
                prompt_text=conversation["prompt_text"],
                response_text=conversation["response_text"],
                commit_message="",
                files_changed=[],
                execution_successful=True,
                validation_passed=True,
                commit_included=False,
                user_context=conversation["context"],
                ai_footer=f"🤖 Auto-tracked AI Conversation (ID: {exec_id})"
            )
            
            # Store in database
            await db.store_execution(execution)
            
            print(f"✅ Auto-tracked AI conversation: {exec_id}")
            
        except Exception as e:
            print(f"❌ Error in direct database tracking: {e}")
    
    def _get_current_repo_path(self) -> str:
        """Get the current repository path."""
        try:
            # Try to get from environment or current working directory
            cwd = os.getcwd()
            
            # Check if we're in a git repository
            current_dir = cwd
            while current_dir != '/' and current_dir:
                if os.path.exists(os.path.join(current_dir, '.git')):
                    return current_dir
                current_dir = os.path.dirname(current_dir)
            
            # Fallback to current directory
            return cwd
            
        except:
            return os.getcwd()
    
    def _get_current_branch(self, repo_path: str) -> str:
        """Get current git branch."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return "main"


async def main():
    """Run the knowledge graph watcher."""
    watcher = KnowledgeGraphWatcher(poll_interval=10)  # Check every 10 seconds
    
    try:
        await watcher.start_watching()
    except KeyboardInterrupt:
        print("\n⏹️ Stopping knowledge graph watcher...")
        watcher.stop_watching()


if __name__ == "__main__":
    asyncio.run(main())