import os
import re
import json
import logging
from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)


def extract_json(text):
    """Extract valid JSON from model output"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in model response")
    return json.loads(match.group(0))


def split_text(text, max_chars=12000):
    """Split long transcript into chunks"""
    chunks = []
    start = 0

    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        start = end

    return chunks


def extract_events_robust(
    transcript_text,
    model="google/gemini-3-flash-preview",
):

    load_dotenv()

    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        base_url="https://openrouter.ai/api/v1",
    )

    # -------- STEP 1 : split transcript --------

    chunks = split_text(transcript_text)

    logger.info("Transcript split into %d chunks", len(chunks))

    partial_events = []

    # -------- STEP 2 : extract events per chunk --------

    for i, chunk in enumerate(chunks):

        system_prompt = """
Tu analyses une transcription de discussion historique.

Identifie les événements passés mentionnés dans ce segment.

Un événement est une action, un changement ou un fait
qui s'est produit dans le passé.

Retourne uniquement du JSON valide :

{
 "events":[
  {
   "title":"...",
   "description":"...",
   "approximate_time":"...",
   "actors":["...","..."],
   "places":["..."],
   "keywords":["...","..."]
  }
 ]
}

Réponds uniquement avec du JSON.
"""

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Segment de transcription :\n\n{chunk}",
                },
            ],
            timeout=120,
        )

        text = completion.choices[0].message.content

        try:
            partial = extract_json(text)
            partial_events.append(partial)
        except Exception:
            logger.warning("JSON parse failed on chunk %d", i)

    # -------- STEP 3 : merge extracted events --------

    events_text = ""

    for p in partial_events:
        for e in p.get("events", []):
            events_text += json.dumps(e, ensure_ascii=False) + "\n"

    # -------- STEP 4 : global event structuring --------

    system_prompt = """
Tu analyses une liste d'événements extraits d'une conversation historique.

Fusionne les doublons et organise les événements.

Retourne du JSON strict :

{
 "events":[
  {
   "title":"...",
   "description":"...",
   "approximate_time":"...",
   "actors":["..."],
   "places":["..."],
   "keywords":["..."]
  }
 ]
}

Réponds uniquement avec du JSON valide.
"""

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""
Événements extraits :

{events_text}
""",
            },
        ],
        timeout=120,
    )

    final_text = completion.choices[0].message.content

    result = extract_json(final_text)

    return result