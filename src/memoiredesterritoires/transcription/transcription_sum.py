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


def summarize_transcript_robust(
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

    partial_summaries = []

    # -------- STEP 2 : summarize each chunk --------

    for i, chunk in enumerate(chunks):

        system_prompt = """
Tu analyses une transcription de conversation.

Résume uniquement ce segment.

Retourne du JSON valide :

{
 "summary": "...",
 "topics": ["...", "..."]
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
            partial_summaries.append(partial)
        except Exception:
            logger.warning("JSON parse failed on chunk %d", i)

    # -------- STEP 3 : merge summaries --------

    summaries_text = "\n".join(
        [p["summary"] for p in partial_summaries if "summary" in p]
    )

    topics_text = "\n".join(
        [", ".join(p.get("topics", [])) for p in partial_summaries]
    )

    # -------- STEP 4 : global analysis --------

    system_prompt = """
Tu analyses une conversation complète.

Crée :

1. un résumé global
2. les thèmes principaux
3. mots clés pour chaque thème

Format JSON strict :

{
 "global_summary": "...",
 "topics":[
  {
   "title":"...",
   "summary":"...",
   "keywords":["...","..."]
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
Résumés partiels :

{summaries_text}

Thèmes détectés :

{topics_text}
""",
            },
        ],
        timeout=120,
    )

    final_text = completion.choices[0].message.content

    result = extract_json(final_text)

    return result