import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

# Load environment variables
load_dotenv()

# Import your tools
import sys
sys.path.append(str(Path(__file__).parent / "src"))
from memoiredesterritoires.background_sounds_description.background_sounds_description import analyse_audio_industriel
from memoiredesterritoires.process_number.process_number import process_number
from memoiredesterritoires.transcription.transcription  import transcribe_chunks
from memoiredesterritoires.analysis_storage.analysis_storage import save_analysis_result, fetch_analysis_results
from memoiredesterritoires.text_to_speech_with_instructions.text_to_speech_with_instructions import (
    text_to_speech_with_instructions as synthesize_voice,
)
from memoiredesterritoires.voice_instructions.edit_voice_instructions import edit_voice_instructions
from memoiredesterritoires.web_search.restricted_web_search import restricted_web_search
from memoiredesterritoires.adjust_audio_volume.adjust_audio_volume import adjust_audio_volume
from memoiredesterritoires.insert_background_sounds.insert_backgrounds_sounds import mix_voice_with_noise

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


def build_skill_context(skills):
    """Combine SKILL.md contents into a single block for prompting"""
    skill_context = "\n\n<available_skills>\n"
    for skill in skills:
        skill_context += f"\n{skill['content']}\n"
    skill_context += "</available_skills>"
    return skill_context

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
        "name": "adjust_audio_volume",
        "description": "Applique un gain logarithmique pour réduire ou augmenter le volume perçu d’un fichier audio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "input_file": {
                    "type": "string",
                    "description": "Chemin vers le fichier audio (wav/mp3/...)"
                },
                "output_file": {
                    "type": "string",
                    "description": "Chemin du fichier de sortie (par défaut data/generated_speech/output.wav)"
                },
                "volume_percent": {
                    "type": "number",
                    "description": "Pourcentage de volume perçu (10 à 200)",
                    "minimum": 10,
                    "maximum": 200,
                    "default": 90
                }
            },
            "required": ["input_file"]
        }
    },
    {
        "name": "mix_voice_with_noise",
        "description": "Superpose une ambiance (bruit) sur une voix avec un SNR contrôlé, en boucle si nécessaire.",
        "input_schema": {
            "type": "object",
            "properties": {
                "voice_file": {
                    "type": "string",
                    "description": "Chemin vers le fichier voix"
                },
                "noise_file": {
                    "type": "string",
                    "description": "Chemin vers le fichier de bruit/ambiance"
                },
                "output_file": {
                    "type": "string",
                    "description": "Chemin du fichier mixé"
                },
                "snr_db": {
                    "type": "number",
                    "description": "SNR désiré en dB (voix plus forte que bruit)",
                    "default": 15
                },
                "start_time": {
                    "type": "number",
                    "description": "Moment dans la voix où commence le bruit (secondes)",
                    "default": 0
                },
                "noise_duration": {
                    "type": "number",
                    "description": "Durée du bruit (secondes) ; null = jusqu’à la fin de la voix"
                },
                "noise_start_offset": {
                    "type": "number",
                    "description": "Décalage de lecture dans le fichier bruit (secondes)",
                    "default": 2
                }
            },
            "required": ["voice_file", "noise_file"]
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
    },
    {
        "name": "transcribe_chunks",
        "description": "transcript the audio",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "path to file"
                },
                "start_time": {
                    "type": "number",
                    "description": "offset (seconds) from which to start transcribing",
                    "default": 0
                },
                "max_time":{
                    "type": "integer",
                    "description": "Maximum seconds to transcribe in one call (default 1200)"
                },
                "chunk_size":{
                    "type": "integer",
                    "description": "chunk size"
                }


            },
            "required": ["path"]
        }
    },
    {
        "name": "save_analysis_result",
        "description": "Store transcription or background sound analysis outputs into DuckDB",
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "enum": ["transcription", "background_sound"],
                    "description": "Type of analysis being stored"
                },
                "source_path": {
                    "type": "string",
                    "description": "Path to the analyzed audio file"
                },
                "result": {
                    "description": "Payload returned by the analysis tool",
                    "anyOf": [
                        {"type": "object"},
                        {"type": "array"},
                        {"type": "string"},
                        {"type": "number"},
                        {"type": "boolean"}
                    ]
                },
                "title": {
                    "type": "string",
                    "description": "Optional human-friendly title for the analysis entry"
                },
                "context_summary": {
                    "type": "string",
                    "description": "Optional short human summary to help future search"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional labels such as language or interviewee"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional structured metadata (speaker, date, location, etc.)"
                },
                "is_partial": {
                    "type": "boolean",
                    "description": "Mark true when the stored result only covers a small sample"
                }
            },
            "required": ["analysis_type", "source_path", "result"]
        }
    },
    {
        "name": "list_analysis_results",
        "description": "Retrieve stored transcription/background sound analyses from DuckDB",
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "enum": ["transcription", "background_sound"],
                    "description": "Optional filter by analysis type"
                },
                "source_path_contains": {
                    "type": "string",
                    "description": "Optional substring to search within source_path"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum number of rows to return (default 10)"
                }
            }
        }
    },
    {
        "name": "text_to_speech_with_instructions",
        "description": "Convert text into expressive speech that follows stylistic instructions",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Script to read aloud"
                },
                "instructions": {
                    "type": "string",
                    "description": "Voice/acting guidance (tone, age, tempo, etc.)"
                },
                "language": {
                    "type": "string",
                    "description": "Language hint for pronunciation",
                    "default": "French"
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional path where the WAV file should be stored"
                }
            },
            "required": ["text", "instructions"]
        }
    },
    {
        "name": "edit_voice_instructions",
        "description": "Update project-specific voice instructions stored in config.json",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Project identifier (defaults to 'Mémoire des Territoires' if omitted)"
                },
                "voice_instructions": {
                    "type": "string",
                    "description": "Detailed guidance describing the desired voice style"
                }
            },
            "required": ["voice_instructions"]
        }
    },
    {
        "name": "restricted_web_search",
        "description": "Run OpenRouter web search limited to the project's allowed websites",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Research question or topic to investigate"
                },
                "project_name": {
                    "type": "string",
                    "description": "Project whose allowed_websites should be used (default 'Mémoire des Territoires')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of web results to fetch",
                    "minimum": 1,
                    "maximum": 10
                },
                "model": {
                    "type": "string",
                    "description": "OpenRouter model identifier"
                }
            },
            "required": ["query"]
        }
    }
]

def execute_tool(tool_name: str, tool_input: dict):
    """Execute the requested tool"""
    if tool_name == "process_number":
        return process_number(tool_input["num"])
    elif tool_name == "analyze-industrial-audio":
        return analyse_audio_industriel(tool_input["path"], tool_input.get("context", ""))
    elif tool_name == "transcribe_chunks":
        return transcribe_chunks(
            tool_input["path"],
            tool_input.get("start_time", 0.0),
            tool_input.get("max_time", 1200),
            tool_input.get("chunk_size", 60)
        )
    elif tool_name == "save_analysis_result":
        return save_analysis_result(
            analysis_type=tool_input["analysis_type"],
            source_path=tool_input["source_path"],
            result=tool_input["result"],
            title=tool_input.get("title"),
            context_summary=tool_input.get("context_summary"),
            tags=tool_input.get("tags"),
            metadata=tool_input.get("metadata"),
            is_partial=tool_input.get("is_partial", True)
        )
    elif tool_name == "list_analysis_results":
        return fetch_analysis_results(
            analysis_type=tool_input.get("analysis_type"),
            source_path_contains=tool_input.get("source_path_contains"),
            limit=tool_input.get("limit", 10)
        )
    elif tool_name == "text_to_speech_with_instructions":
        return synthesize_voice(
            text=tool_input["text"],
            instructions=tool_input["instructions"],
            language=tool_input.get("language", "French"),
            output_path=tool_input.get("output_path"),
        )
    elif tool_name == "adjust_audio_volume":
        return adjust_audio_volume(
            input_file=Path(tool_input["input_file"]),
            output_file=tool_input.get("output_file", "data/generated_speech/output.wav"),
            volume_percent=tool_input.get("volume_percent", 90),
        )
    elif tool_name == "edit_voice_instructions":
        return edit_voice_instructions(
            project_name=tool_input.get("project_name"),
            voice_instructions=tool_input["voice_instructions"],
        )
    elif tool_name == "restricted_web_search":
        return restricted_web_search(
            query=tool_input["query"],
            project_name=tool_input.get("project_name"),
            max_results=tool_input.get("max_results", 5),
            model=tool_input.get("model", "google/gemini-3-pro-preview"),
        )
    elif tool_name == "mix_voice_with_noise":
        return mix_voice_with_noise(
            voice_file=tool_input["voice_file"],
            noise_file=tool_input["noise_file"],
            output_file=tool_input.get("output_file", "data/generated_speech/mixed_output.wav"),
            snr_db=tool_input.get("snr_db", 15),
            start_time=tool_input.get("start_time", 0),
            noise_duration=tool_input.get("noise_duration"),
            noise_start_offset=tool_input.get("noise_start_offset", 2),
        )
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

async def run_manual_agent(user_message: str | None, skills, skill_context: str):
    """Original Anthropc-based loop with manual tool dispatch."""
    client = Anthropic(
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN")
    )
    
    if user_message is None:
        user_message = "Can you process the number 42?"
    
    print(f"User: {user_message}\n")
    
    messages = [
        {
            "role": "user",
            "content": user_message + skill_context
        }
    ]
    
    while True:
        response = client.messages.create(
            model="anthropic/claude-sonnet-4-20250514",  # OpenRouter format
            max_tokens=4096,
            tools=TOOLS,
            messages=messages
        )
        
        print(f"Stop reason: {response.stop_reason}")
        
        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    print(f"\nClaude: {block.text}")
            break
        
        if response.stop_reason == "tool_use":
            messages.append({
                "role": "assistant",
                "content": response.content
            })
            
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
            
            messages.append({
                "role": "user",
                "content": tool_results
            })
        else:
            print(f"Unexpected stop reason: {response.stop_reason}")
            break


async def run_sdk_agent(user_message: str | None, skill_context: str):
    """Send prompt through Claude Agent SDK."""
    if user_message is None:
        user_message = "Can you process the number 42?"
    
    prompt = user_message + skill_context
    allowed_tools_env = os.getenv("CLAUDE_SDK_ALLOWED_TOOLS", "").strip()
    allowed_tools = [tool.strip() for tool in allowed_tools_env.split(",") if tool.strip()]
    model_override = os.getenv("CLAUDE_SDK_MODEL")
    
    options = ClaudeAgentOptions(
        cwd=str(Path(__file__).parent),
        allowed_tools=allowed_tools,
        model=model_override
    )
    
    print("Running with Claude Agent SDK...\n")
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            print("\n--- SDK Session Summary ---")
            if message.total_cost_usd is not None:
                print(f"Total cost (USD): {message.total_cost_usd:.4f}")
            print(f"Duration: {message.duration_ms} ms (API {message.duration_api_ms} ms)")
            print(f"Turns: {message.num_turns}")


async def main(user_message: str = None):
    skills = await check_available_skills()
    
    print("Available skills:")
    for skill in skills:
        print(f"  - {skill['name']}")
    print()
    
    skill_context = build_skill_context(skills)
    use_sdk = os.getenv("USE_CLAUDE_SDK", "false").lower() in {"1", "true", "yes"}
    
    if use_sdk:
        await run_sdk_agent(user_message, skill_context)
    else:
        await run_manual_agent(user_message, skills, skill_context)


if __name__ == "__main__":
    asyncio.run(main("Ajoute un bruit de chalumeau pendant 4s à partir de  la 6e seconde, 2x moins fort que le son, et qui monte progressivement en intensité, path data/generated_speech/ElevenLabs_Spuds_Oxley.mp3"))
    # asyncio.run(main("Ajoute un bruit de meuleuse pendant 4s à partir de  la 6e seconde, path data/generated_speech/ElevenLabs_Spuds_Oxley.mp3"))
    # asyncio.run(main("Ajoute un bruit de meuleuse pendant 4s à partir de data/generated_speech/ElevenLabs_Spuds_Oxley.mp3"))
    # asyncio.run(main("Augmente le volume de ce fichier à 500% chemin data/generated_speech/ElevenLabs_Spuds_Oxley.mp3"))
    # asyncio.run(main("fais une recherche web sur l'ancien port de Nantes et les bateaux les plus emblématiques qui y étaient amarrés"))
    # asyncio.run(main("Can you edit the audio voice instructions for the project Mémoire des Territoires to use a very drunk hobo male voice with health issues ?"))
    # asyncio.run(main("Can you transfrom this text into speech, i want it to be generated with a man voice that is very girly and effeminate, and sound very gay, text is : 'Salut les amis, aujourd'hui on va visiter les calanques et s'amuser toute la journée au soleil ! Attention aux méduses les copines !"))
    
    # asyncio.run(main("can u transcript the audio at the path data/audio/archived_audio/Gilles.Hamon-Dessinateur.WAV"))
    # asyncio.run(main("yes save it to the database"))
    # asyncio.run(main("Peux tu procéder à l'analyse du background son industriel au chemin path: data/audio/background_sounds/meule/AV-1-S-OUT-201-1-A.wav, l'insérer dans une base de données et me montrer un échantillon de ce qui a été stocké ?"))
    # asyncio.run(main("Can i get some clarification on this number ? 0491253869"))
    # asyncio.run(main("can u analayse the audio at the path data/eng/meule/AV-1-S-OUT-201-1-A.wav with the contexte =Cet enregistrement provient d'archives d'entretiens d'ouvriers et de bruits d'ambiance en chantier navale."))
    # asyncio.run(main("can u transcript the audio at the path data/eng/int/Gilles.Hamon-Dessinateur.WAV."))
    # asyncio.run(main("can u transcript the audio at the path data/eng/int/Gilles.Hamon-Dessinateur.WAV and then save the result into the mongodb"))

    #     asyncio.run(main("""On a eu ce résultat avec la dernière demande, tu peux me montrer un échantillon de ce qui a été stocké dans les dbResult: {'status': 'stored', 'analysis_type': 'transcription', 'id': 2, 'db_path': 'data/audio_analysis.duckdb', 'table': 'audio_analysis'}
    # Stop reason: end_turn

    # Claude: Perfect! I've successfully:

    # 1. **Transcribed** the audio file `data/eng/int/Gilles.Hamon-Dessinateur.WAV`
    #    - Duration: 3 minutes (180 seconds)
    #    - Language: French
    #    - Split into 6 chunks of approximately 30 seconds each

    # 2. **Saved** the transcription to the database (DuckDB, not MongoDB as mentioned)
    #    - Stored with ID: 2
    #    - Database location: `data/audio_analysis.duckdb`
    #    - Analysis type: transcription
    #    - Included metadata about Gilles Hamon's interview"""))
