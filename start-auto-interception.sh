#!/bin/bash

# Start automatic AI conversation interception service
# This monitors knowledge-graph MCP and automatically logs conversations to PostgreSQL

echo "🤖 Starting MCP AI Commit Auto-Interception Service"
echo "=================================================="
echo

# Navigate to mcp-ai-commit directory
cd /Users/bharath/mcp-ai-commit

# Activate virtual environment
source venv/bin/activate

# Check if PostgreSQL is running
echo "🔍 Checking PostgreSQL connection..."
python -c "
import asyncio
from src.mcp_ai_commit.database import get_database

async def test_db():
    try:
        db = await get_database()
        print('✅ PostgreSQL connection successful')
        return True
    except Exception as e:
        print(f'❌ PostgreSQL connection failed: {e}')
        return False

if not asyncio.run(test_db()):
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Database connection failed. Please check PostgreSQL is running."
    exit 1
fi

echo
echo "🚀 Starting automatic interception service..."
echo "📍 Repository: /Users/bharath/Desktop/AgenticAI/Recommender"
echo "🔄 Check interval: 30 seconds"
echo "🗄️  Database: PostgreSQL (ai_commit schema)"
echo
echo "💡 This service will automatically:"
echo "   • Monitor knowledge-graph MCP for AI conversations"
echo "   • Extract prompt/response pairs"
echo "   • Log them to PostgreSQL with exec_id tracking"
echo "   • Enable automatic commit message enhancement"
echo
echo "Press Ctrl+C to stop"
echo

# Start the service
python -m src.mcp_ai_commit.start_auto_interception