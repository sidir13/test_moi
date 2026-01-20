import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions
from dotenv import load_dotenv
import os

# Environment variables should be set before running:
# ANTHROPIC_BASE_URL=https://openrouter.ai/api
# ANTHROPIC_AUTH_TOKEN=your_openrouter_api_key
# ANTHROPIC_API_KEY=""

load_dotenv()  # Load environment variables above from .env file

print(os.getenv("ANTHROPIC_BASE_URL"))
async def main():
    async for message in query(
        prompt="Find and fix the bug in auth.py",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Bash"]
        )
    ):
        print(message)

asyncio.run(main())

# npm install @anthropic-ai/claude-agent-sdk

# brew install nvm