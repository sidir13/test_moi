import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
import json

# Load environment variables
load_dotenv()

# Import your tools
import sys
sys.path.append(str(Path(__file__).parent / "src"))
from memoiredesterritoires.background_sounds_description.background_sounds_description import analyse_audio_industriel
from memoiredesterritoires.process_number.process_number import process_number

async def check_available_skills():
    """Check and list available skills from SKILL.md files"""
    skills_dir = Path("src/memoiredesterritoires")
    available_skills = []
    
    if skills_dir.exists():
        for tool_dir in skills_dir.iterdir():
            if tool_dir.is_dir():
                skill_file = tool_dir / "SKILL.md"
                if skill_file.exists():
                    with open(skill_file, 'r') as f:
                        content = f.read()
                    available_skills.append({
                        "name": tool_dir.name,
                        "path": str(skill_file),
                        "content": content
                    })
    
    return available_skills

# Define available tools for Claude
TOOLS = [
    {
        "name": "process_number",
        "description": "Multiply a number by 2",
        "input_schema": {
            "type": "object",
            "properties": {
                "num": {
                    "type": "integer",
                    "description": "The number to process"
                }
            },
            "required": ["num"]
        }
    },
    {
        "name": "analyze-industrial-audio",
        "description": "analyse the audio",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "path to file"
                },
                "context":{
                    "type": "string",
                    "description": "contexte general"
                }

                
            },
            "required": ["path"]
        }
    }
]

def execute_tool(tool_name: str, tool_input: dict):
    """Execute the requested tool"""
    if tool_name == "process_number":
        return process_number(tool_input["num"])
    elif tool_name == "analyze-industrial-audio":
        return analyse_audio_industriel(tool_input["path"], tool_input.get("context", ""))
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

async def main(user_message: str = None):
    # Check available skills
    skills = await check_available_skills()
    
    print("Available skills:")
    for skill in skills:
        print(f"  - {skill['name']}")
    print()
    
    # Build skill context
    skill_context = "\n\n<available_skills>\n"
    for skill in skills:
        skill_context += f"\n{skill['content']}\n"
    skill_context += "</available_skills>"
    
    # Initialize Anthropic client
    client = Anthropic(
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN")
    )
    
    # User query
    if user_message is None:
        user_message = "Can you process the number 42?"
    
    print(f"User: {user_message}\n")
    
    # Initial messages
    messages = [
        {
            "role": "user",
            "content": user_message + skill_context
        }
    ]
    
    # Agentic loop
    while True:
        response = client.messages.create(
            model="anthropic/claude-sonnet-4-20250514",  # OpenRouter format
            max_tokens=1024,
            tools=TOOLS,
            messages=messages
        )
        
        print(f"Stop reason: {response.stop_reason}")
        
        # Check if we're done
        if response.stop_reason == "end_turn":
            # Extract text response
            for block in response.content:
                if block.type == "text":
                    print(f"\nClaude: {block.text}")
            break
        
        # Handle tool use
        if response.stop_reason == "tool_use":
            # Add assistant response to messages
            messages.append({
                "role": "assistant",
                "content": response.content
            })
            
            # Execute tools
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n🔧 Calling tool: {block.name}")
                    print(f"   Input: {block.input}")
                    
                    result = execute_tool(block.name, block.input)
                    print(f"   Result: {result}")
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })
            
            # Add tool results to messages
            messages.append({
                "role": "user",
                "content": tool_results
            })
        else:
            # Unexpected stop reason
            print(f"Unexpected stop reason: {response.stop_reason}")
            break

if __name__ == "__main__":
    #asyncio.run(main("Can i get some clarification on this number ? 0491253869"))
    asyncio.run(main("can u analayse the audio at the path data/eng/meule/AV-1-S-OUT-201-1-A.wav with the contexte =Cet enregistrement provient d'archives d'entretiens d'ouvriers et de bruits d'ambiance en chantier navale."))
