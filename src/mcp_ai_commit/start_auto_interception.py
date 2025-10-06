#!/usr/bin/env python3
"""
Startup script to begin automatic interception of Claude Code conversations.
This bridges knowledge-graph MCP to ai-commit system for automatic logging.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

from .auto_bridge import start_auto_interception, get_auto_bridge

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutoInterceptionService:
    """Service to run automatic interception in the background."""
    
    def __init__(self):
        self.bridge_manager = None
        self.running = False
        
    async def start(self, check_interval: int = 30):
        """Start the automatic interception service."""
        logger.info("Starting Automatic AI Conversation Interception Service")
        logger.info("=" * 60)
        logger.info(f"Knowledge Graph → AI Commit Bridge")
        logger.info(f"Check interval: {check_interval} seconds")
        logger.info(f"Target repository: /Users/bharath/Desktop/AgenticAI/Recommender")
        logger.info("=" * 60)
        
        try:
            # Start the bridge
            self.bridge_manager = await start_auto_interception(check_interval)
            self.running = True
            
            logger.info("✅ Automatic interception started successfully!")
            logger.info("🔍 Monitoring knowledge graph for AI conversations...")
            logger.info("💾 Auto-logging to PostgreSQL database")
            logger.info("")
            logger.info("Press Ctrl+C to stop")
            
            # Keep the service running
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, shutting down...")
            await self.stop()
        except Exception as e:
            logger.error(f"❌ Error starting automatic interception: {e}")
            await self.stop()
    
    async def stop(self):
        """Stop the automatic interception service."""
        self.running = False
        if self.bridge_manager:
            self.bridge_manager.stop()
        logger.info("✅ Automatic interception service stopped")
    
    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point for the automatic interception service."""
    service = AutoInterceptionService()
    service.setup_signal_handlers()
    
    # Default check interval of 30 seconds
    check_interval = 30
    
    # Allow override from command line
    if len(sys.argv) > 1:
        try:
            check_interval = int(sys.argv[1])
            logger.info(f"Using custom check interval: {check_interval} seconds")
        except ValueError:
            logger.warning(f"Invalid interval '{sys.argv[1]}', using default: {check_interval}")
    
    await service.start(check_interval)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)