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
from memoiredesterritoires.transcription.transcription  import transcribe_audio
from memoiredesterritoires.analysis_storage.analysis_storage import save_analysis_result, fetch_analysis_results
from memoiredesterritoires.text_to_speech_with_instructions.text_to_speech_with_instructions import (
    text_to_speech_with_instructions as synthesize_voice,
)
from memoiredesterritoires.voice_instructions.edit_voice_instructions import edit_voice_instructions
from memoiredesterritoires.voice_instructions.generate_voice_instructions import generate_voice_instructions
from memoiredesterritoires.web_search.restricted_web_search import restricted_web_search
from memoiredesterritoires.adjust_audio_volume.adjust_audio_volume import adjust_audio_volume
from memoiredesterritoires.insert_background_sounds.insert_backgrounds_sounds import mix_voice_with_noise
from memoiredesterritoires.background_sound_finder.background_sound_finder import find_background_sounds
from memoiredesterritoires.elevenlabs_tts.elevenlabs_tts import eleven_labs_tts
from memoiredesterritoires.scenario_maker import ScenarioMakerSkill
from memoiredesterritoires.project_config_builder import ScenarioConfigBuilderSkill

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


# Instantiate complex skills once
scenario_maker_skill = ScenarioMakerSkill()
project_config_builder_skill = ScenarioConfigBuilderSkill()

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
        "name": "eleven_labs_tts",
        "description": "Génère une narration via ElevenLabs (à utiliser seulement si l'utilisateur le demande explicitement)",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Script à synthétiser"
                },
                "voice_id": {
                    "type": "string",
                    "description": "Identifiant ElevenLabs de la voix"
                },
                "model_id": {
                    "type": "string",
                    "description": "Modèle ElevenLabs à utiliser",
                    "default": "eleven_multilingual_v2"
                },
                "output_path": {
                    "type": "string",
                    "description": "Chemin du fichier MP3 de sortie"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "find_background_sounds",
        "description": "Liste les fichiers audio disponibles dans data/audio/background_sounds pour aider à choisir un bruit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Terme à rechercher dans les noms de dossiers/fichiers"
                },
                "limit": {
                    "type": "integer",
                    "description": "Nombre maximum de résultats",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20
                }
            }
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
        "name": "transcribe_audio",
        "description": "Split a WAV audio file into fixed-size chunks and transcribe each chunk using OpenRouter (Gemini), returning a full transcription with timestamps.",
        "input_schema": {
            "type": "object",
            "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the WAV audio file"
            },
            "chunk_duration_s": {
                "type": "integer",
                "description": "Chunk size in seconds",
                "default": 30,
                "minimum": 1,
                "maximum": 1200
            },
            "model": {
                "type": "string",
                "description": "OpenRouter multimodal model to use",
                "default": "google/gemini-3-flash-preview"
            }
            },
            "required": ["path"]
        }
    }
        ,
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
                "project_name": {
                    "type": "string",
                    "description": "Project whose stored voice instructions should be used"
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
        "name": "generate_voice_instructions",
        "description": "Generate and store voice instructions based on a historical/cultural scenario",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario": {
                    "type": "string",
                    "description": "Description du contexte/texte à restituer"
                },
                "project_name": {
                    "type": "string",
                    "description": "Projet ciblé (défaut: Mémoire des Territoires)"
                },
                "hint_language": {
                    "type": "string",
                    "description": "Langue du scénario (guide le prompt)",
                    "default": "French"
                }
            },
            "required": ["scenario"]
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
    },
    {
        "name": "build_project_scenario_config",
        "description": "Parse a textual brief plus archival resources to create a project-specific scenario_config JSON.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_description": {
                    "type": "string",
                    "description": "Narrative description of the new project (history, tone, audience, etc.)"
                },
                "mode": {
                    "type": "string",
                    "description": "simple = parse prompt, expert = merge provided JSON",
                    "enum": ["simple", "expert"],
                    "default": "simple"
                },
                "project_config_path": {
                    "type": "string",
                    "description": "Path to an existing project config to merge (expert mode)"
                },
                "base_config_path": {
                    "type": "string",
                    "description": "Base config JSON to start from (default config/default_config.json)"
                },
                "output_path": {
                    "type": "string",
                    "description": "Destination path for the adapted configuration"
                },
                "project_name": {
                    "type": "string",
                    "description": "Override metadata.project_name"
                },
                "audio_transcriptions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file_name": {"type": "string"},
                            "transcription": {"type": "string"},
                            "language": {"type": "string"},
                            "notes": {"type": "string"},
                            "source": {"type": "string"}
                        },
                        "required": ["file_name", "transcription"]
                    },
                    "description": "Optional transcripts to include in user_provided audio sources"
                },
                "documents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                            "source": {"type": "string"}
                        },
                        "required": ["content"]
                    },
                    "description": "Optional textual documents to store alongside the config"
                }
            },
            "required": ["project_description"]
        }
    },
    {
        "name": "generate_historical_scenario",
        "description": "Run the Mémoire des Territoires multi-agent pipeline to create scenarios and timelines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "User prompt in simple mode"
                },
                "mode": {
                    "type": "string",
                    "enum": ["simple", "expert"],
                    "default": "simple",
                    "description": "simple = provide prompt, expert = use expert_config/expert_config_path"
                },
                "config_path": {
                    "type": "string",
                    "description": "Path to base scenario configuration JSON"
                },
                "output_dir": {
                    "type": "string",
                    "description": "Directory where scenarios and timelines should be written"
                },
                "audio_transcriptions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file_name": {"type": "string"},
                            "transcription": {"type": "string"},
                            "language": {"type": "string"},
                            "notes": {"type": "string"},
                            "source": {"type": "string"}
                        },
                        "required": ["file_name", "transcription"]
                    },
                    "description": "Optional transcripts to inject before running the pipeline"
                },
                "expert_config_path": {
                    "type": "string",
                    "description": "Config file to use in expert mode"
                },
                "persist_updated_config": {
                    "type": "boolean",
                    "description": "Save the enriched config alongside outputs",
                    "default": False
                },
                "updated_config_path": {
                    "type": "string",
                    "description": "Explicit path for the saved config copy"
                }
            }
        }
    }
]

def execute_tool(tool_name: str, tool_input: dict):
    """Execute the requested tool"""
    if tool_name == "process_number":
        return process_number(tool_input["num"])
    elif tool_name == "analyze-industrial-audio":
        return analyse_audio_industriel(tool_input["path"], tool_input.get("context", ""))
    elif tool_name == "transcribe_audio":
        return transcribe_audio(
            tool_input["path"],
            tool_input.get("chunk_duration_s", 30),
            tool_input.get("model", "google/gemini-3-flash-preview")
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
            project_name=tool_input.get("project_name"),
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
    elif tool_name == "generate_voice_instructions":
        return generate_voice_instructions(
            scenario=tool_input["scenario"],
            project_name=tool_input.get("project_name"),
            hint_language=tool_input.get("hint_language", "French"),
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
    elif tool_name == "eleven_labs_tts":
        return eleven_labs_tts(
            text=tool_input["text"],
            voice_id=tool_input.get("voice_id", "pqHfZKP75CvOlQylNhV4"),
            output_path=tool_input.get("output_path"),
            model_id=tool_input.get("model_id", "eleven_multilingual_v2"),
        )
    elif tool_name == "find_background_sounds":
        return find_background_sounds(
            keyword=tool_input.get("keyword"),
            limit=tool_input.get("limit", 20),
        )
    elif tool_name == "build_project_scenario_config":
        return project_config_builder_skill.run(tool_input)
    elif tool_name == "generate_historical_scenario":
        return scenario_maker_skill.run(tool_input)
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
    asyncio.run(main("We need you to use your availables skills to properly generate the audio narrated scenario throught tts based on scenario conig file at data/scenarios/chantiers_navals/scenarios/scenario_2_20260204_172233.json, you can extract the story that is divided into different part into the different texte_narration keys of the json ! Generate the audio file with the text to speech too"))
    # asyncio.run(main("""Peux tu modifier le fichier config par défaut pour la génération de scénarios et en générer un nouveau à partir de cet extrait d'interview et informations:
                     
    #     Le projet concerne donc le port de Nantes-Saint-Nazaire, plus précisément les chantiers navals de Nantes, avec un focus sur les ouvriers travaillant dans les années 60-80. L'objectif est de capturer l'expérience des ouvriers à travers leurs témoignages, en mettant en lumière les conditions de travail, la culture ouvrière, et l'évolution des chantiers navals durant cette période.
    #     On veut ici vraiment mettre l'accent sur le parcours de vin d'un ouvrier dans ces années là et faire des scénarios certains mélancoliques et certains le racontant comme une histoire extrêmement heureuse et excitante.
                     
    #     Interview:          
    #     Alors l'idée c'est qu'après, dès que j'ai fini, je vais recommencer à retranscrire. Vu qu'après je retranscris tout, j'ai besoin, pour commencer, qu'est-ce que vous pourriez me donner votre nom, votre prénom et votre âge ? Amon, Gilles. Oui. Votre âge ? 73. Très bien. Alors, avez-vous travaillé au chantier ? Oui. Si oui, où ? Dans quel chantier vous avez travaillé ?

    #     Au départ, c'était la Bretagne, à 14 ans, puis on a suivi toutes les fusions, pour faire venir au chantier de Nantes et puis au chantier du Bujon, ça s'est appelé comme ça, qui était la fusion des trois chantiers nantais de la région. Jusqu'à quelle période ? Jusqu'à la fermeture-fermeture ? En 78, par là, puis après j'ai viré à Saint-Nazaire. D'accord, à Saint-Nazaire. Et vous avez fini votre carrière là-bas ? Ah bah oui. D'accord. Qu'est-ce que vous vous rappelez de votre date d'embauche au tout début ?

    #     Ah bah oui, c'était au mois de septembre. D'accord. Je ne sais plus, 78 par là. L'année, vous vous en rappelez ? Oh, euh... 43, euh... Soit 58. 58. 58, 58, 59, c'est ça. Oui, c'est ça. D'accord, donc en septembre 58. Quel était votre poste au niveau des chantiers ? Est-ce qu'il a évolué au fil des années ? On a commencé comme apprenti, naturellement, puis après ouvrier.

    #     Alors, en tant qu'ouvrier traceur, on était déjà très bien placé dans les groupes, il y avait... Et puis après, je suivais des cours à l'ivette, qui m'a permis de passer le brevet, qui m'a permis de monter tout de suite au dixième, puis en parallèle, après j'avais suivi les cours de dessin, pas de dessinateur, puis je suis passé au bureau de dessin. D'accord. Et puis à Chauffa, je grimpais en grade. D'accord.

    #     Et comme j'étais bien vu, j'ai souvent eu des galons. D'accord. Au fil des années ? Au fil des années. En traversant les différentes fusions. D'accord. Donc, en quoi consistait votre travail, plus précisément ? Au départ, il fallait étudier et faire les formes des bateaux, suivant des données, que l'on avait des bureaux d'études, des points. Dans l'espace, soit en largeur, en longueur, en profondeur.

    #     Et puis par terre, représenter ça sous une forme de dessin. Alors c'est allé chez l'un, donc c'était sur un parquet. Donc on travaillait à quatre pattes par terre. D'accord. Sur les photons qu'on connaît ? Oui, il fallait avec un décamètre, reporter des points qu'on nous donnait, puis penser une latte, puis voir que les points, si on se fait à la latte, bien naturellement, ça faisait tout de travers. Alors c'était à nous de refaire une belle ligne droite, et à ce moment-là, de reporter les points qu'on avait corrigés, et comme ça.

    #     Et après, à la fin, c'était accepté par l'armateur ou son représentant, bien naturellement. D'accord. Donc ça, ça a été une partie. Est-ce que ça a évolué avec le temps, avec les nouvelles techniques ? Ah ben naturellement, alors c'était ça, c'est pour ça qu'on suivait des cours tout le temps, parce que ça a duré un certain moment, ça. Et dans les autres chantiers, c'était pareil. Et puis après, il y a eu le traçage au dixième. C'est-à-dire que tout le dessin que l'on faisait à l'échelle, il fallait le faire... Au dixième de la taille, plus petit.

    #     Dix fois plus petit. Mais c'est même pas tout à fait ça. On dessinait... Ça revenait à un dessin sur une table, qui n'était plus pareil. Avec, mettons, un mètre ou un décimètre, où il y a les graduations. D'accord. Mais on s'est servi du double pour dessiner au dixième de millimètre près, qui était indiqué sur l'instrument de mesure. Oui, parce que si vous utilisiez des grandes tailles, ça faisait en réalité des beaucoup plus petits dessins. Ah bah oui, là, je vais vous montrer un ballon bleu.

    #     On le verra pas à l'heure. Non, non, c'est ça. Là, quand on a un décamètre, un mètre, là, c'était du matériel allemand qui est très très très précis, qui ne bouge pas. J'en ai encore, où il y a les centimètres, puis les millimètres, là. Et nous, il fallait faire un dessin, mettons, un trêve, c'était le dixième de millimètre de là, divisé en dix. Donc, c'était, ouais, d'accord, c'était, ok. Comme ça, alors avec une loupe. Donc, vraiment. Et hop, tout, tout, tout petit.

    #     Tout petit, et hop, là. Et il n'y avait qu'un côté qui compte. D'accord. Si bien qu'on s'en fout de l'épaisseur. Mais au dixième près, parce qu'après, mettons, notre rectangle qu'on avait fait, c'était, le dessin allait à une machine qui reproduisait en dix fois plus grand. D'accord. Donc, la moindre erreur a été multipliée par dix. D'accord. C'est ça le truc. Mais c'était dans tous les chantiers pareil. Alors, les trucs en forme, pareil. Le développement. Il fallait tout développer, mais au dixième près. À la loupe, on avait des loupes. Donc, c'était vraiment un travail de précision sur les plans pour que, quand ce soit ressorti à la bonne taille.

    #     C'était multiplié par dix. La moindre augurrence d'un côté ou de l'autre. D'accord. Et c'est là qu'on avait fait, moi j'avais été, et ainsi d'autres, faire un, pas un stage, mais en déplacement, à la suite de la version, à l'époque, sur le concorde. Parce que c'était pareil. Ils ont dessiné au dixième près, là-bas aussi. Sur un panneau, pas sur du papier. Et c'était reproduit, mais au dixième. C'était pas multiplié par dix. D'accord. Parce que c'était mécanique. Au lieu que ce soit un chalumeau qui coupe, c'était une pièce qui tournait comme ça, puis qui découpait, suivant notre trait.

    #     Mais au dixième près. Et c'était reproduit sur la pièce, mais au dixième près, pareil. C'était pas multiplié. D'accord. Donc, l'erreur restait au dixième près. C'était vrai. Au lieu de que ce soit agrandi dix fois, c'était exactement la même chose. Parce que c'est mécanique. C'était retranscrit directement. D'accord. C'est comme ça. D'accord. C'est pour ça que j'avais été là-bas, puis, oh, j'avais voulu me faire embaucher, enfin, j'avais mis un truc pour faire embaucher, parce qu'il s'était payé plus cher. C'était mieux payé. Ah oui, oui. Puis après, ça avait remonté quand même, le chantier.

    #     Ça s'est allé. Ah bah oui. Alors, on a suivi ça au dixième, et puis après, moi, j'avais passé, en même temps, je continuais, j'avais passé le sérapé de dessin. Et puis, quand j'ai eu, un moment, je suis tombé à un moment où, il n'y avait pas besoin de dessinateur. Donc, j'y allais. Et puis, des fois, tu me dis, ah, il y en avait besoin. Et hop, je vais monter. Alors, je pensais, des fois, elle montait. Mais je faisais toujours partie du dixième, quand même. Mais j'avais monté en grade. Donc, au niveau de vos postes, vous avez eu ce moment où vous traciez sur le plancher.

    #     Vous avez eu le moment où vous avez travaillé sur les plans au dixième. Et ensuite, comment ça a évolué après ça ? C'est resté comme ça jusqu'à la fin ? Ah non, non. Le dixième, après, c'est passé à l'ordinateur. D'accord. Et à ce moment-là, moi, j'étais au bureau d'études. C'est bien que je n'ai pas trop travaillé. Je ne sais comment que c'est, mais je n'ai pas travaillé à l'ordinateur en tant que traceur. D'accord. Parce que j'étais déjà débalancé. J'étais dessinateur, dessinateur. J'ai fini dessinateur-projeteur.

    #     C'est comme ça l'appellation qui fait partie des codes. J'ai fini comme ça. Après, moi, je n'ai pas suivi. Parce qu'arrivés là-bas, à Saint-Nazaire, eux, ils avaient déjà leur traceur et tout ça. Donc, j'ai plutôt été viré là-bas à Saint-Nazaire, au bureau de Dès. D'accord. Donc, je n'ai pas travaillé à l'ordinateur pour développer les tôles et tout. D'accord. Donc, vous, vous travailliez plus, techniquement, sur la structure générale. Ah oui. Sur la structure générale d'un bateau. Oui. Et puis, ce qu'il y a au chantier, souvent, on faisait, mettons, quatre bateaux pareils. Donc, nous, on n'avait plus de travail. D'accord. Vous avez juste à le dupliquer quatre fois.

    #     Ah oui. Donc, vous n'allez pas nous payer. Ils m'avaient viré, puis les collègues aussi, dans le bureau d'études, mais d'ici de la menuiserie. D'accord. Parce que les bateaux, l'extérieur étant pareil, mais l'intérieur change. Ils en profitent. Il y a eu des cabines en plus, des trucs en moins. Alors, ça donne du boulot. Et quand j'étais à Saint-Denis-Azer, j'ai été viré au bureau d'études aménagement. D'accord. Parce qu'ils avaient déjà leur taulier. Puis, c'est là que j'ai grimpé au bureau d'études aménagement, là-bas.

    #     Très bien. C'est faire les aménagements, c'est tout l'intérieur, tout. Alors là, ça change de bateau en bateau. Comme là, ils vont en avoir quatre pareilles. La coque extérieure est la même. Elle est la même, mais par contre, l'intérieur va être chamblé. Totalement différent. Il y a tout ce qui arrive dans l'industrie pendant un an, qui ne pouvait pas se faire dans ce bateau-là. Donc, il y a forcément des améliorations à chaque fois. On a vu ça à chaque coup. Ou alors, ça coûtait trop cher. Ah ben, tiens, on va le mettre dans celui-là. D'accord. C'est toujours une histoire d'argent, mais ce n'est pas mon problème.

    #     Chacun son job. Donc, vous avez vu que mon travail, c'est lié avec la discussion qu'on avait eue mardi sur la grue jaune, les engins de levage, les différentes petites choses qu'on peut retrouver. Donc, si vous avez été embauché sur les chantiers à la fin des années 50, Jean Pénaud m'avait dit que lui, il avait vu la grue jaune se monter en 58. Bon, mais nous, on n'est qu'à l'apprentissage. Est-ce que c'était de l'autre côté ? C'était loin de…

    #     Ah non, mais oui, mais nous, on était… La Bretagne qui était là, et la roue jaune faisait partie de la Loire qui était à côté. Donc, c'était un peu… Ah oui. C'était un autre… C'était une autre… Vu que c'était une autre entreprise, vous ne m'éliangiez pas avec ces personnes-là ? Oh oui, mais on connaissait les gens. Parce qu'à l'époque, on s'enculait avec notre chef, on prenait la clé sur la porte, comme on dit, on s'en va. Et puis, on s'en bougeait à côté. Il n'y avait pas de chômage à l'époque. Très bien. Et puis, on était prêtés. Moi, j'étais prêté souvent à Chantenay, là-bas, à Dubujon.

    #     D'accord. C'était un peu plus… Une autre façon de faire à Chantenay, enfin, ça paraissait plus vieux que nous. Plus à l'ancienne ? Oui, oui, plus à l'ancienne. Eux, ils mettaient des morceaux de bateau comme ça les uns sur les autres, comme on fait chez nous. Mais il y avait du bon partout. D'accord, oui, c'est ce que vous me racontiez. L'autre aussi, du bon. Et après, il y avait une armée de découpeurs partout. Alors, tout d'un coup, on parlait, brum, l'autre écoupait, là. Brum, tout tombait. Alors que nous, nous, quand il y avait une épaisseur, à la limite, il y avait du bon.

    #     Mais quand celle-là était bonne, tout de suite, ils mettaient l'épaisseur au-dessus. Jusqu'là, voilà, tout. En l'espace de peu de temps, les gens d'à côté, ils voyaient le bateau se faire. D'après, tout d'un coup, bam, bam, bam, oh là là. C'était une autre façon de faire. Mais ce n'était pas des gros bateaux comme maintenant. Ils ne pourraient pas. Ils pouvaient se permettre ça parce que c'était des plus petites structures. Ah oui, oui, oui. Puis souvent, c'était des bateaux qu'on avait été, je m'appelle, c'était des pinardiers, tout que ça. C'est vide à l'intérieur. Ce n'est pas des paquebots. Donc, il n'y a pas besoin de gros aménagements. Oui, oui. Donc, ils pouvaient se permettre d'empiler et puis après la couper.

    #     Alors, si vous avez travaillé sur les chantiers dans les années 50, est-ce que vous n'avez pas vu l'agrojaune se construire ? Ah non. Mais en tout cas, vous l'avez vu pendant longtemps travailler. Ah oui, on l'a vu, oui, oui. D'accord. Donc, la question normalement que je pose, mais là, techniquement, je suppose que c'est d'une autre manière, c'est est-ce que votre pose était liée à l'utilisation des gros, souvent parce que c'est des charpentiers fer, donc des personnes qui étaient dans les cales, enfin dans les ateliers et en train de... Oui, ils avaient besoin de la grue. Voilà. Mais est-ce que vous avez assisté, par exemple, à des destructions, des modifications de grue ? Parce que si vous étiez là à la fin, au milieu des années 70 ? Ah bah oui, j'étais là. Parce qu'il y a des travaux qui ont été faits sur la grue au milieu des années 70. Ah oui, elle a été mis, ils ont renforcé. Ah là, exactement. Alors, ils avaient mis, on a vu ça, on m'a pas demandé de visu, ils ont apporté des gros blocs, tout dans le bas de la grue, ils l'ont monté en charge ou en puissance. Donc, ils ont amené des blocs de béton, qui étaient coulés de la vente, pour faire une assise beaucoup plus lourde. Oui. J'ai vu que ça, moi. Vous avez juste vu ça dans... Ça, c'était dans les... De ce que j'ai recommandé, c'est dans les années 70, en 74. Vous n'avez pas de souvenirs des travaux qui ont été faits, parce que j'ai vu un article de journal où un ancien de la société Montalède expliquait qu'ils avaient soulevé la flèche de la grue pour modifier le... Bon, je vais vous tenir à l'angle. Il va falloir que j'utilise le mot, ça vous ferait. Oui, mais non, il suffit que j'étais... Comme c'était grand en surface, le bateau, il fallait le chanter, il suffit de travailler à ce bout-là, c'est que c'était loin, ça dépasse. De l'autre côté de l'avenue, là, dans le temps de la Bretagne, mais de l'autre côté, ça faisait partie des chantiers. Il y a toute une histoire, là, quand... Il y avait la grue, là, et on allait de l'autre côté, là, il y avait les parcs à taules, à profiler. Les taules n'étaient pas, ils allaient pas les traverser, donc c'était des parcs à profiler. Et en passant, chacun avait sa place dans les cafés, là. On regardait Ratatintin à la télévision.

    #     On se tournait, il y avait nos chefs derrière, mais personne ne disait rien, parce que moi, je suis arrivé à la vague, ça. Il faut dire que chaque travail avait un temps. Donc les chefs, à la limite, ils s'en foutaient, ils voyaient les gobs. Parce que si tellement le travail était fait, c'était fait. Bah oui, mais s'il ne passait plus de temps qu'il fallait, il avait un malus, c'est le dessous en moins, sur sa paille. Donc les chefs, à la limite, ils ne disaient rien. On va dire que c'est arrêté. Donc voilà, on peut continuer.

    #     Par contre, si on avait du temps, on avait des galons. Mais il fallait que le travail soit bien fait. Il ne faut pas le... Alors nous, en tant que crasseurs, comme je dis souvent, on n'avait pas la grue, pas besoin de grue, parce que ceux qui avaient besoin de grue, s'il fallait qu'ils attendent une heure, la grue, ça faisait une heure de leur temps à moins. D'accord. S'ils étaient deux, il fallait être au moins deux heures de temps. À la fin, trop de temps. Allez, crac. D'accord. Parce qu'eux, il y avait ce...

    #     Alors, je ne sais pas si je m'exprime bien, mais ce système de le temps comptabilisé pour faire quelque chose, il avait son problème. Parce que si les personnes s'appuyaient entre eux, en plus, si le grutier connaît du retard, ça impactait aussi les autres. Au maximum, il n'y a que deux grues par bateau. Il fallait bien qu'il y avait du... Oui, ça ne soit pas non-définie que ça, parce qu'il y avait des corporations. Le gars, il démarrait son travail avec du malus. Dès le départ, il y avait des... Alors, ça ne collait plus. Alors, il y avait le bureau des pleurs, que ces gens-là, il fallait bien qu'ils se défendent. Donc, ils expliquaient, puis souvent, ça s'arrangeait. Et qui c'était le bureau des pleurs ? C'est des anciens traceurs, comme moi, qui étaient trop vieux pour faire le tracé par terre. Alors, si j'allais pigner, j'avais tout ce que je voulais. Mais enfin, ça ne s'est jamais arrivé. Nous, on avait du temps. Parce qu'on faisait nos formes de bateaux. Si ça ne plaisait pas aux lieux, ils pensaient, ah non, c'est pas ça. Bon, il faudrait effacer ça. Un peu plus de forme, là. Bon, on s'en fiche, nous. Vous étiez moins soumis à cette réglementation-là.

    #     C'est pour ça qu'il y avait des corporations. Alors, c'est pour ça que ça s'est battu, ça, au niveau syndicat et tout ça. Puis, moi, j'ai vécu que la fin de ça. After, ça a été supprimé. Ils ont arrangé moyen à tout le monde et terminé. Il n'y avait plus, il n'y avait plus ce marchandage. Et il n'y avait pas construit, on ne sait pas que c'était partout. Oui, alors, ça n'allait plus, ça. Alors, vu que vous étiez sur les chantiers à cette période-là, question un peu étrange peut-être, est-ce que, je suppose que vous n'avez pas trop côtoyé des groutiers ou des personnes qui… On ne les connaissait pas que ça, on ne les connaissait pas. On ne les connaissait pas, mais la question, c'est, est-ce que ces personnes-là, par exemple, vu que le goutier est parfois séparé du reste, est-ce qu'eux, ils étaient un peu enviés par le fait qu'ils n'étaient pas dans le travail en bas ? Enfin, ça, il faut aller demander. Il n'est pas là où… Le gars qui est… L'électricien de service qu'on a là, il s'occupe justement de l'électricité des grouts et tout. Alors, lui, il connaît tous les… Ah oui, c'est lui.

    #     Ah oui, moi, je n'avais pas affaire aux gens des grouts. Et au niveau de la… Parce que le chantier était quand même… Il y avait un paquet de grues à l'intérieur du chantier. Ah oui, les photos, là. Il y en avait un petit paquet, j'ai vu sur certains plans, qu'il y en avait entre 10 et 15. Ah oui, peut-être bien. Est-ce que c'était impressionnant à voir au niveau de la machinerie, de la taille que c'était ? Nous, c'est quand on est rentré dans l'apprentissage, à 14-15 ans, comme vous voyez ça, puis après on est dans le mouvement, on marche entre les grues, c'est l'univers des grues. C'est ça, à la fin, c'était le paysage de tous les jours. C'est la ferroie partout. Oui, ben oui. Les bateaux, ils se construisaient entre deux rangées de grues, enfin, deux brunes de chaque côté, puis l'autre à côté, pareil. Mardi, on avait discuté du fait qu'il y avait eu des différents petits accidents qu'il y avait eu sur des grues, qui avaient été en surpoids, des élargues qui avaient craquées. Il n'y a pas eu d'embêtement, pas spécialement, je veux dire, il n'y a pas eu d'accident grave. Il n'y a pas eu d'accident grave, non. C'est arrivé de temps en temps, par exemple, qu'une élame claque pendant... Moi, ça m'était arrivé à moi, à tracer quelque chose. Les tôles, on les mettait sur un grottis en ferroi, comme ça, puis ils arrivaient par la grue, et puis, soit qu'il y avait une grue qui était mal, enfin, elle était, c'était... Des pinceaux tousseurs. Oui, ou elle aurait été mal servie. Et puis, tout d'un coup, paf, elle est tombée sur le... Ben, j'aurais été là, alors que j'étais à côté, moi. Elle vous est tombée juste à côté. Elle est tombée, oh, ben, merde ! C'est un truc qu'on réagit après.

    #     Ben, soit que la grue, la tôle, elle a dû accrocher un moment, puis ça s'est décroché, et claque, parce que c'est un système de pincement. C'est le poids de... C'est le poids qui fait serrer la pince. Oui, dès que tout n'est pas... Ben, ça s'écroche. Alors, pour moi, elle avait dû faire ça, puis claque. Puis, moi, j'étais à côté, je me dis, paf ! Oh, bon, bon, ben, c'est après, les collègues, ben, elle te serait tombée dessus. Ben, oui, sur le coup, on n'y pense pas. Oh, ben, ça, c'est des trucs comme ça. Ah, mais, non, il n'y a pas eu d'accident. Alors, la fameuse... Quand c'est tout le bloc, là, là, là, là, il y aurait pu avoir des accidents. Est-ce que vous pourriez me raconter ça, parce que là, pour que je puisse le réécrire. Là, vous voyez, là, il y avait la grue, l'emplacement, oui, la grue, les deux rails étaient là, et puis la grue était là. Et puis, moi, j'étais juste à côté, là. Il y avait un panneau de tôle, avec plusieurs tôles. Puis, moi, j'étais à tracer des éléments. Et puis, après, ce patelot, là, à cet emplacement-là, ben, ils mettent des affaires dessus. Et puis, ça fait un morceau. Donc, ça fait un ensemble de choses à soulever d'un seul coup. Après, ben, là, il était vide, puisque là... Et puis, la grue, ben, elle est à côté de moi, là. Donc, ça, c'était laquelle de grue, tu ne penses pas ? Alors, c'est une grue, une grue noire à sa route.

    #     Deuxième partie : de 1200 à 2400 secondes
    #     Alors, c'est une grue, une grue noire à sa route. Et c'est justement, c'est là, je parlais de ça. La grue, le pied, la grue, ben, je sais bien, il était juste, moi, j'étais là. Et il y a, je crois qu'il y a au moins quatre roues. Il y en a qui disent quatre ou six roues, mais un ensemble comme ça. Et puis, le roi qui est là. Et puis, moi, j'étais à côté. Et puis, quand on est à quatre pattes, là, ben, on est à cette hauteur-là. À la hauteur des galets des roues. Et la roue, il y a un bloc au milieu. Alors, ça, je me rappellerai toujours, comme ça.

    #     Et puis, là, il y a un axe. Et puis, après, il y a le reste de la grue. Et il y a tout un système qui vient accrocher, là. Ça, ça fait partie de la grue. Là, c'est en deux fois, comme ça, il y a un axe. Et puis, il y a le reste de la grue, là. Et moi, j'étais à côté. Et c'est ça qui s'est soulevé. À un moment, elle, elle a été là. Donc, en fait, le pied... Oui, oui. Ça, il est resté par terre. En fait, les... Les roues. Si on peut expliquer, les roues sont restées sur le sol. Mais en fait, la tige centrale s'est soulevée. Oui, oui. Mais comment c'est possible que la grue soit soulevée, alors ? Ben, c'est en haut. Avec la force. C'est ça. Il y avait deux grues, au départ. Il y avait cette grue, là. Et puis, il y en avait une autre. Et c'était un bloc qui était accroché. C'était des escorteurs. Et en haut, parce que quand c'est fait, là, tout est fait à l'envers. De par la forme du bateau.

    #     Autrement, ça serait en équilibre. C'est fait à l'envers. Il y a renversé toutes les formes pour pouvoir les construire en avance. Là, comme ça. C'est une surface plane. Ça commence par le fond du bateau qui est comme ça. Bon, nous, dans les ateliers et par terre, il les fabrique comme ça, avec les éléments. C'était un morceau comme ça, justement. After, ils mettent la tôle par-dessus, qui s'arrête par là. Et après, l'ensemble est soulevé. Et puis, ils le retournent. Donc, c'était un morceau comme ça. Mais plus compliqué. Pas un fond.

    #     C'était une serpente arrière ou une serpente à quelque... Un truc quand même assez lourd. Volumineux. Volumineux, oui. Volumineux. Oh, ben, lourd. C'est plein de vide, à l'intérieur. À la limite, c'est plus lourd, les bocs du fond. Parce qu'ils ont des éléments dans ce sens-là. Et ça fait un quadrillage. À la limite, ils sont plus lourds par eux-mêmes que celui de l'avant, mettons, qui est plein de vide. Mais qui est beaucoup plus volumineux. Ça, c'était un crochet comme ça. Et ça cassait. À un moment, il a basculé.

    #     Et tout le poids a été sur celle-là. D'accord. Donc, il y a un bout de la structure qui s'est brisé. Donc, une attache. Il y avait deux grues qui portaient chacune à côté. Et puis après, de façon de... Un mouvement de fait. Au moment où il y en avait une qui lâchait un peu plus de... Oui, mais à ce moment-là, il repose à un moment. Parce qu'il ne faut pas qu'il loge. Donc, pour la retourner, alors, ils vont dans un endroit où il repose. Là, il loge. Et après, il se rattache d'une autre façon.

    #     De façon d'arriver à leur tourner. D'accord. Mais là, il s'est cassé. Et claque. En pleine... En l'air. Alors, tout d'un coup, elle a basculé. Et tout le poids a été là. Alors, comme j'étais là. Puis moi, ça a soulevé. C'est signe qu'à la limite, c'est en face. Puisqu'elle a fait ça, les pieds. Donc, c'est hop. Donc, en fait, tout le poids est tombé sur la flèche. Et ça a soulevé la grue à la palier. Donc, c'était de l'autre côté où j'étais, moi. Il faut que ça s'est soulevé, là. C'est de l'autre côté. C'est pour ça que je n'ai rien eu, moi. After, j'ai vu ça. Puis, on a entendu le bruit. Tous les boulons qu'on pétait, les écrous. En fait, c'est à cause de la surtention. Les boulons qui étaient dans la structure ont sauté. Ah, bah oui. Il y a eu trop de poids, tout d'un coup. Il y a eu un choc. Tout ça, parce que ça a été soudé dans l'eau. Il pleuvait à plein temps. D'accord. Oui, d'accord. Donc, vu qu'il pleuvait, c'était moins soudé. La soudure avait été... Et puis, il y un truc, comme disait Coler, qui était dans ce bureau-là. Ça tourne autour d'un centre de gravité.

    #     Et puis, ils s'obéissent. Les opérateurs et tout, là. Ils obéissent au plan qui existe, qui a été fait. Et là, c'était tout nouveau. Ce n'était pas vieux. Before, ça n'existait pas, ça. Donc, le fait de définir des centres de gravité, des choses comme ça. Parce qu'avant, les charges n'avaient pas foncièrement besoin d'être calculées comme ça. C'était pas... C'était l'habitude. Ils savaient. Parce que ça a été dur, des fois. Il y a certains chocs qui n'ont pas voulu obéir au plan. D'accord. Moi, on a l'habitude de faire ça comme ça. Et puis, ils ont été obligés. Après, il y a les assurances.

    #     Alors là, c'est des goussets qui... Mettre des goussets, il y a la ferroi qui est là. Et puis, des goussets, c'est un truc comme ça, qui est triangulaire. Et puis, il y a un trou dedans où on passe les angles. Cette forme-là, en gros, elle est triangulaire. Et puis, il y a le trou pour laisser passer. Et puis, souvent, il y a... En plus, des goussets de déversement, c'est ça qu'ils parlaient. D'accord. Donc, les goussets... Si ça appuie là... Ben oui, il ne faut pas que ça arrache la tôle. Alors, il paraît que les goussets... C'est vrai qu'ils n'étaient pas mis parce que...

    #     C'est une histoire de temps. Parce que le temps, c'est de l'argent. Ben oui. C'est vraiment si, en fait, on perd du temps à mettre des goussets... Ben oui. On perd du temps de... Ou alors, ils étaient mis, mais ils n'étaient pas soudés. Donc, en fait, l'idée, ce serait que le gousset qui servait, en fait, à tirer... Ben, ça a été tiré... Il a été mal fait, ou alors, il n'avait pas de goussets de déversement. Et puis, en plus, ça a été soudé dans l'eau, dans la puits. Et ça refroidit trop vite, ça. Donc, le moindre choc, ben, ça sautait. Alors, s'il y en a un qui pète, l'autre pète tout de suite.

    #     Et puis, à ce moment-là, ben, oh là... Ça faisait un bruit. Ben oui, moi, j'étais de l'autre côté. Il y a tellement de bruit dans le chantier. Un bruit qu'on ne se tourne pas. Oh, ben, c'est un bruit de plus, quoi. Et c'est là, quand j'ai vu tout le... J'ai vu en face. Oh ! Et puis, j'ai vu, heureusement, qu'il est retombé bien sur ses pattes. Oh, ben, autrement, ça aurait été la fin de tout. Elle ne bougeait pas dans ce sens-là, la groute. Oh, ben, elle aurait bougé dans ce sens-là, c'est fini. Pour un peu qu'il ne tombait pas dans l'axe, oui. Donc, sa chance, c'est qu'en fait, ce soit tombé tout droit. Peut-être pas un peu comme ça, comme ça.

    #     Mais elle ne bougeait pas dans ce sens-là. C'est dans ce sens-là. Et alors, l'autre, elle a dû sûrement avoir quelque chose. L'autre aussi, sûrement, à un moment, elle s'est trouvée libérée. Et l'autre, il y a dû avoir aussi quelque chose. Alors, le pantonnier tout là-haut, là, c'est quoi, c'est la figure, lui ? Dans sa caline. S'il fait mal au genou, il paraît qu'il ne peut jamais remonter, après. Alors, c'est en haut, les grues, qui sont comme ça. Et puis, or, ben, l'accrochage... C'est tous les boulons qu'il tenait, là. C'est tout ça, quoi. Donc, tous les boulons qu'il tenait la flèche.

    #     Qui a fléché. Qui a porté. Alors, clac, clac, clac, il y a une pluie de boulons qui est tombée. On n'a pas entendu parler qu'il y a eu de blesser, ni rien du tout. Ben non, parce que, comme je disais là, quand ils font des manœuvres comme ça, ben, allez, il ne faut pas rester de souverain. On ne peut pas... Parce que, en dehors de ça, mais souvent, des oublis, ça arrive souvent. Des boîtes de soudure, ça arrive. Puis, plein. On retourne, on retourne, tout à l'heure, tout à l'heure. Quelqu'un qui avait oublié sa boîte de soudure à l'intérieur. Oui, en gros, c'est un exemple. Ça pouvait arriver. Oui, oui, c'est pour ça qu'il fallait...

    #     Ben oui, il y avait toujours des cochonneries. Pour attacher les bouts de ferreuil, comme pour les fils, pour les souder à leur place, on pique sur le sol un bout de ferreuil, comme ça, et puis on met un coin. Un coin qui est comme ça. Et puis, on tape un coup de marteau. Parce que le tracé, il est là, mettons. Alors, en tapant un coup de marteau, ça ramène la ferreuil comme ça. Clac. Hein, puis, quand ces points, quand la ferreuil est le long du trail, on fait un point de soudure, puis après, on casse notre morceau. Mais il reste là. Donc, il y a plein de morceaux de ferreuil qui ne donnent pas de coup de balai. C'est bon. Allez, on entend tout ce qui... Oui, de toute façon, on se met pas dessus. Vous avez assisté souvent des... Je suppose, là, si vous étiez parfois, de temps en temps, au pied de la grue, en train de dessiner. Vous avez souvent vu des utilisations comme ça. Je suppose qu'avec le temps, si vous avez vu une longue période qui s'écoule jusque dans les années 70, comment ça a évolué, cette relation entre le grutier, enfin, le pontonnier, et les personnes qui étaient en bas en train de travailler, au niveau de comment ils communiquaient entre eux ? On m'a dit qu'ils travaillaient au début par gestes, s'ils n'avaient pas de radio. Est-ce que c'était quelque chose ou c'était un peu une entente sous-entendue ou est-ce que c'est quelque chose qui se faisait vraiment avec des signes qui étaient prédéfinis ? Des signes, oui, parce que souvent, nous, on ne le voyait pas, donc c'était un troisième individu, c'est lui qui faisait des signes.

    #     Donc, c'était un peu l'intermédiaire entre le sol et le grutier. D'abord, le grutier, souvent, il est tourné de l'autre côté, alors pour l'appeler, rien n'est. Ah, il y avait le dé... Moi, j'ai connu, puis c'est vrai, mais il y avait des téléphones à la grue. Il fallait tourner la manivelle et puis hop, on... C'était en bas de la grue ? Oui, accroché à son côté. Accroché à la grue. C'est un genre de téléphone avec une dynamo, quoi, pour... Oui, il fallait tourner et puis, allô, oui, ça y est, allez, viens, j'ai besoin, alors derrière, puis après, il y a un qui faisait... Hop, hop, hop. Puis alors après, oui, il y en avait un qui faisait des gestes, stop, stop, stop, stop. Parce que tous ceux qui... Il y avait une équipe de gars qui étaient des cadors. C'est tous ceux qui mettaient les zélingues et tout ça. Parce que ce n'est pas des gars comme moi. Moi, je faisais mes blocs et tout, mais après, c'était des zélingueurs. Tout ça, puis c'était des embarréglages. Parce que c'était les zélingues et les manies, c'est assez lourd. C'est eux qui parlaient bien. Alors là, ils savaient, tal, tal, tal, tal.

    #     Allez, ils montent. Parce qu'après, ces gros blocs, une fois qu'ils étaient bien retournés et tout, ça permettait, entre eux, de finir la soudure. Au lieu de faire une soudure au plafond, comme c'était retourné, impeccable. Et puis, finir les quelques éléments qu'on ne pouvait pas faire. Il y en a qu'on pouvait... Quand on leur tournait, au trois quarts, le bloc était fini. Un bloc de qu'est-dessous, là. Pratiquement, à 100%, ils étaient finis en dessous. À la limite, quand ils leur tournaient, il y avait quelques soudures à faire, là. Mais c'est tout. Parce que... Souvent, c'était un panneau qui était... Les tôles étaient déjà soudés, mettons, des deux côtés qui enveloppaient ou leur fait vraiment une forme. Donc, une fois qu'ils les terminaient comme ça, à la limite, il y avait quelques soudures comme ça. Et souvent, ah ben si, et puis les soudures, si, pour tenir quand même les viroles qui étaient là, les soudures de dessous, ben oui, il faut bien. Au lieu de les faire au plafond, il n'y en avait qu'un tout petit peu et après, ils les faisaient à la main. Mais il fallait quand même... Ah ben non, même pas parce que... Pour soulever, lui, eh ben, les crochets, enfin, les blocs, je veux dire, les pitons, étaient plutôt là sur les côtés. Ici, ici. Mais pas, pas là. D'accord. Plus sur l'intérieur de... Oui, et puis, dans ce sens-là déjà, bon ben, ils étaient sur les côtés. D'accord. Parce que ça finissait par une tôle. Même si la tôle avait des trous, il y avait forcément de la tôle.

    #     Qui fermait le... Qui fermait une section. Donc c'était accroché là. D'accord. Et puis l'autre côté, pareil. Donc la grue, les prenaient là. Il y avait deux grues qui prenaient. After, il y en avait une qui lochait. Alors là, c'était le truc le plus simple. Elle prenait. L'autre est loche. Puis à un moment, il touche par terre. Donc en gros, ça faisait ça. Alors il soulevait. Puis il y avait le poids. Oui, c'était pas simple. Parce qu'à un moment, il soulevait tout seul. Et à ce moment-là, le passage, il le repensait là. D'accord. Il faisait ça. Et puis, ils arrivaient à le retourner.

    #     Ça, c'était assez simple. Oui, c'était... Parce qu'après, une fois qu'il était comme ça, il faisait sauter les manis qui étaient là. Et il soudait quatre manis carrément dessus après. Parce qu'il était bien. Et après, il le prenait comme ça. C'était... Ça faisait 100 tonnes au maximum. Parce que ça pouvait... Soudait 100 tonnes. Oui, c'est ça. Elle toute seule. Donc la grande grue jaune, elle se permettait de soulever... Elle toute seule. Mais est-ce qu'elle pouvait soulever vraiment 100 tonnes ? Parce que dans les années 70, elle... Non, elle avait été montée à 100 tonnes.
                     
    #                  """))
    # asyncio.run(main("Can you use the tts elevelabs tool to generate speech for the text: 'Bonjour à tous, ceci est un test de synthèse vocale avec ElevenLabs.'"))
#     asyncio.run(main("""Peux tu générer l'audio pour ce texte:
                     
#                      Imaginez la Loire en 1950. Les chantiers navals de Nantes bourdonnaient d'activité.
# Des coques immenses prenaient forme sous les mains expertes des soudeurs et des charpentiers.
# Le paquebot France, fierté nationale, est né ici en 1960. Cent six mille tonnes de rêves et d'acier.
# Aujourd'hui, seules les grues jaunes témoignent de ce passé glorieux."""))
    # asyncio.run(main("""Peux tu déterminer les instructions de voix idéales pour le scénario suivant ? Au milieu du dix-huitième siècle, Nantes s'affirme comme l'un des ports les plus actifs du royaume. La construction navale se professionnalise : un quai des constructions s'aménage en aval de la Chézine, tandis que les charpentiers s'installent à la Piperie. Nantes devient alors le premier constructeur de navires marchands de France et se lance dans la production de bâtiments de guerre.
    # Le dix-neuvième siècle marque l'apogée de cette industrie. En mille huit cent soixante et un, la compagnie Penhoët est fondée, insufflant un nouvel élan à l'industrie navale nantaise. Les Chantiers Dubigeon, créés dès mille sept cent soixante, deviennent une référence mondiale. Entre mille huit cent quatre-vingt-neuf et mille neuf cent deux, ils lancent vingt-six grands trois-mâts, dont le célèbre Belem en mille huit cent quatre-vingt-seize, le plus vieux voilier d'Europe encore en service aujourd'hui.
    # Les Trente Glorieuses représentent le sommet de cette aventure industrielle : jusqu'à sept mille salariés travaillent sur les trois sites nantais. Mais la concurrence étrangère, l'ensablement de la Loire et la baisse des commandes précipitent le déclin. En mille neuf cent quatre-vingt-sept, les Chantiers Dubigeon ferment définitivement leurs portes, tournant la dernière page de trois siècles de construction navale à Nantes. L'île de Nantes entame alors sa métamorphose, du territoire industriel au quartier de la création."""))
    # asyncio.run(main("can u transcript the audio at the path data/audio/archived_audio/Gilles.Hamon-Dessinateur.WAV"))
    # asyncio.run(main("Peux tu procéder à l'analyse des 2 premières minutes de l'interview au path: data/audio/archived_audio/Gilles.Hamon-Dessinateur.WAV , l'insérer dans une base de données et me montrer un échantillon de ce qui a été stocké ?"))
    # asyncio.run(main("Peux tu procéder à l'analyse du background son Titanier et l'insérer dans une base de données et me montrer un échantillon de ce qui a été stocké ?"))
    # asyncio.run(main("Peux tu procéder à l'analyse du background son industriel au chemin path: data/audio/background_sounds/meule/AV-1-S-OUT-201-1-A.wav, l'insérer dans une base de données et me montrer un échantillon de ce qui a été stocké ?"))
    # asyncio.run(main("Ajoute un bruit de chalumeau pendant 4s à partir de  la 6e seconde, 2x moins fort que le son, et qui monte progressivement en intensité, path data/generated_speech/ElevenLabs_Spuds_Oxley.mp3"))
    # asyncio.run(main("Ajoute un bruit de meuleuse pendant 4s à partir de  la 6e seconde, path data/generated_speech/ElevenLabs_Spuds_Oxley.mp3"))
    # asyncio.run(main("Ajoute un bruit de meuleuse pendant 4s à partir de data/generated_speech/ElevenLabs_Spuds_Oxley.mp3"))
    # asyncio.run(main("Augmente le volume de ce fichier à 500% chemin data/generated_speech/ElevenLabs_Spuds_Oxley.mp3"))
    # asyncio.run(main("fais une recherche web sur l'ancien port de Nantes et les bateaux les plus emblématiques qui y étaient amarrés"))
    # asyncio.run(main("Can you edit the audio voice instructions for the project Mémoire des Territoires to use a very drunk hobo male voice with health issues ?"))
    # asyncio.run(main("Can you transfrom this text into speech, i want it to be generated with a man voice that is very girly and effeminate, and sound very gay, text is : 'Salut les amis, aujourd'hui on va visiter les calanques et s'amuser toute la journée au soleil ! Attention aux méduses les copines !"))
    

    # asyncio.run(main("""Peux tu changer les instructions de Voix en 'Voix posée, maîtrisée et assurée' et Peux tu transformer ce text en speech ? Au milieu du dix-huitième siècle, Nantes s'affirme comme l'un des ports les plus actifs du royaume. La construction navale se professionnalise : un quai des constructions s'aménage en aval de la Chézine, tandis que les charpentiers s'installent à la Piperie. Nantes devient alors le premier constructeur de navires marchands de France et se lance dans la production de bâtiments de guerre.
    # Le dix-neuvième siècle marque l'apogée de cette industrie. En mille huit cent soixante et un, la compagnie Penhoët est fondée, insufflant un nouvel élan à l'industrie navale nantaise. Les Chantiers Dubigeon, créés dès mille sept cent soixante, deviennent une référence mondiale. Entre mille huit cent quatre-vingt-neuf et mille neuf cent deux, ils lancent vingt-six grands trois-mâts, dont le célèbre Belem en mille huit cent quatre-vingt-seize, le plus vieux voilier d'Europe encore en service aujourd'hui.
    # Les Trente Glorieuses représentent le sommet de cette aventure industrielle : jusqu'à sept mille salariés travaillent sur les trois sites nantais. Mais la concurrence étrangère, l'ensablement de la Loire et la baisse des commandes précipitent le déclin. En mille neuf cent quatre-vingt-sept, les Chantiers Dubigeon ferment définitivement leurs portes, tournant la dernière page de trois siècles de construction navale à Nantes. L'île de Nantes entame alors sa métamorphose, du territoire industriel au quartier de la création."""))
    # asyncio.run(main("can u transcript the audio at the path data/audio/archived_audio/Gilles.Hamon-Dessinateur.WAV"))
    # asyncio.run(main("yes save it to the database"))
    # asyncio.run(main("Peux tu procéder à l'analyse du background son industriel au chemin path: data/audio/background_sounds/meule/AV-1-S-OUT-201-1-A.wav, l'insérer dans une base de données et me montrer un échantillon de ce qui a été stocké ?"))
    # asyncio.run(main("Can i get some clarification on this number ? 0491253869"))
    # asyncio.run(main("can u analayse the audio at the path data/eng/meule/AV-1-S-OUT-201-1-A.wav with the contexte =Cet enregistrement provient d'archives d'entretiens d'ouvriers et de bruits d'ambiance en chantier navale."))
    # asyncio.run(main("can u transcript the audio at the path data/eng/int/Gilles.Hamon-Dessinateur.WAV."))
    # asyncio.run(main("can u transcript the audio at the path data/eng/int/Gilles.Hamon-Dessinateur.WAV and then save the result into the db"))

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
