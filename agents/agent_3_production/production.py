"""
Agent 3: Audio Tag Engineer
Takes a scenario from Agent 2 and produces text annotated with:
  - ElevenLabs voice tags  : [pause 2s], [rire], [murmure], [ton grave], …
  - Ambient sound markers   : {ambiance_port_brume.wav}, {foule_agitee.wav}, …

The output is a single text string (per scenario) that can be fed directly
to ElevenLabs TTS and a sound-design pipeline.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ProductionEngineerAgent:
    """Agent 3: Produces ElevenLabs-tagged text from a written scenario."""

    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5"
        self.temperature = 0.3
        self.max_tokens = 8000

        self.system_prompt = (
            "Vous êtes un ingénieur de production audio spécialisé dans le "
            "balisage de textes pour la synthèse vocale ElevenLabs v3 et le "
            "design sonore.\n\n"
            "Votre rôle est de prendre un scénario narratif et d'y insérer :\n"
            "1. Des **Audio Tags ElevenLabs v3** entre crochets [] — ils sont "
            "interprétés nativement par le modèle eleven_v3 (pas lus à voix haute).\n"
            "   Utilisez UNIQUEMENT les tags v3 officiels suivants :\n"
            "   - Pauses / rythme  : [pause], [précipité], [ralentit], [posé], [étire]\n"
            "   - Réactions vocales: [rit], [soupire], [chuchote], [crie], [bégaye]\n"
            "   - Émotions         : [triste], [en colère], [joyeusement], [timidement]\n"
            "   - Accentuation     : [accentué], [atténué], [interrogatif]\n"
            "   ⚠️ N'inventez PAS de tags hors de cette liste — ils seraient lus "
            "à voix haute.\n"
            "2. Des **marqueurs de sons d'ambiance** entre accolades {} — ils "
            "indiquent où insérer des fichiers audio d'ambiance (traités séparément).\n"
            "   Exemples : {ambiance_port_brume.wav}, {foule_agitee.wav}, "
            "{clapotis_eau.wav}, {vent_mer.wav}, {pas_sur_paves.wav}.\n\n"
            "Règles générales :\n"
            "- Insérez les tags [] DANS le texte, au bon endroit pour que "
            "la lecture soit naturelle et émotionnellement juste.\n"
            "- Les marqueurs {sons} se placent en début de paragraphe ou "
            "à des transitions narratives importantes.\n"
            "- Ne modifiez JAMAIS le texte narratif lui-même (pas de réécriture).\n"
            "- Soyez subtil : pas trop de balises — un balisage excessif "
            "nuit à la qualité.\n"
            "- Nommez les fichiers d'ambiance de manière descriptive : "
            "snake_case, extension .wav.\n"
            "- Adaptez l'intensité et le type des balises au ton du scénario.\n\n"
            "Règle spéciale — CITATIONS [ARCHIVE : « … »] :\n"
            "ElevenLabs v3 ne permet pas de changer de voix dans un seul appel, "
            "mais vous pouvez différencier vocalement les citations en enveloppant "
            "leur contenu avec des tags qui créent un contraste avec la narration.\n"
            "Utilisez systématiquement ce schéma autour de chaque citation :\n"
            "  [posé] [atténué] « texte de la citation » [pause]\n"
            "Ce combo rend la citation plus calme, légèrement retenue — "
            "comme une voix qui émerge du passé — distinct du ton narratif.\n"
            "Si la citation est émotionnelle (colère, tristesse), remplacez "
            "[atténué] par le tag émotionnel approprié ([triste], [en colère]…).\n"
            "Exemple complet :\n"
            "  Jean raconte : [posé] [atténué] « J'avais dix-huit ans, "
            "je venais juste d'arriver. » [pause] Le chantier l'attendait."
        )

        # Legacy skills (kept for backward compat)
        self.sound_selector = None
        self.timeline_composer = None

        logger.info("ProductionEngineerAgent initialized (ElevenLabs tagging mode)")

    def set_skills(self, skills: Dict):
        """Set skill instances (legacy)."""
        if "ambiance_sound_selector" in skills:
            self.sound_selector = skills["ambiance_sound_selector"]["instance"]
        if "audio_timeline_composer" in skills:
            self.timeline_composer = skills["audio_timeline_composer"]["instance"]

    # ==================================================================
    # NEW primary entry point: ElevenLabs tagging
    # ==================================================================

    def formatWithTags(
        self,
        scenario: Dict[str, Any],
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Annotate a scenario's narration with ElevenLabs voice tags
        and ambient sound markers.

        Parameters
        ----------
        scenario : dict
            Complete scenario output from Agent 2
            (must contain ``parties`` with ``texte_narration``).
        config : dict, optional
            Pipeline config (used for voice_instructions, ton, etc.).

        Returns
        -------
        dict with keys:
            scenario_id, titre, taggedText, parties (with per-part tagged text),
            metadata.
        """
        scenarioId = scenario.get("scenario_id", 1)
        titre = scenario.get("titre", "Scénario")
        logger.info("Formatting scenario %d with ElevenLabs tags", scenarioId)

        # ---- Collect context for the LLM ----
        voiceInstructions = ""
        ton = ""
        if config:
            voiceInstructions = (
                config.get("voice_instructions", "")
                or config.get("scenario_config", {}).get("voice_instructions", "")
            )
            ton = (
                config.get("scenario_config", {})
                .get("generation_parameters", {})
                .get("ton", {})
                .get("value", "")
            )
        # Fallback ton from scenario
        if not ton:
            ton = scenario.get("ton", "neutre_informatif")

        notesAgent3 = scenario.get("notes_pour_agent_3", "")

        # ---- Build the full narration text with part markers ----
        partTexts: List[str] = []
        partMeta: List[Dict] = []
        for part in scenario.get("parties", []):
            pid = part.get("partie_id", "?")
            titre_part = part.get("titre", "")
            texte = part.get("texte_narration", "")
            tonPart = part.get("ton", {})
            if isinstance(tonPart, dict):
                tonGlobal = tonPart.get("global", "")
                intonation = tonPart.get("intonation", "")
            else:
                tonGlobal = str(tonPart)
                intonation = ""

            # Ambiance hints from Agent 2
            ambianceHints = []
            for amb in part.get("ambiances_continues", []):
                if isinstance(amb, dict):
                    desc = amb.get("description", amb.get("son", ""))
                    if desc:
                        ambianceHints.append(desc)

            momentHints = []
            for mc in part.get("moments_cles", []):
                if isinstance(mc, dict):
                    action = mc.get("action", "")
                    desc = mc.get("description", mc.get("consigne", ""))
                    if action or desc:
                        momentHints.append(f"{action}: {desc}" if desc else action)

            partTexts.append(
                f"=== PARTIE {pid} : {titre_part} ===\n"
                f"[ton: {tonGlobal}] [intonation: {intonation}]\n"
                f"Ambiances suggérées: {', '.join(ambianceHints) if ambianceHints else 'aucune'}\n"
                f"Moments clés: {', '.join(momentHints) if momentHints else 'aucun'}\n\n"
                f"{texte}"
            )
            partMeta.append(
                {"partie_id": pid, "titre": titre_part, "original_text": texte}
            )

        fullNarration = "\n\n".join(partTexts)

        # ---- Build prompt for LLM ----
        prompt = self._buildTaggingPrompt(
            fullNarration, ton, voiceInstructions, notesAgent3
        )

        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                system=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            taggedText = response.content[0].text.strip()

            # ---- Split back into per-part tagged texts ----
            taggedParts = self._splitTaggedTextByParts(taggedText, partMeta)

            result = {
                "scenario_id": scenarioId,
                "titre": titre,
                "taggedText": taggedText,
                "parties": taggedParts,
                "metadata": {
                    "voiceTags": self._countTags(taggedText, r"\[.*?\]"),
                    "soundTags": self._countTags(taggedText, r"\{.*?\}"),
                    "originalWordCount": sum(
                        len(re.findall(r"\b\w+\b", p["original_text"]))
                        for p in partMeta
                    ),
                },
            }

            logger.info(
                "Tagging done — %d voice tags, %d sound tags",
                result["metadata"]["voiceTags"],
                result["metadata"]["soundTags"],
            )
            return result

        except Exception as e:
            logger.error("Error in formatWithTags: %s", e, exc_info=True)
            # Fallback: return untagged text
            return {
                "scenario_id": scenarioId,
                "titre": titre,
                "taggedText": fullNarration,
                "parties": [
                    {
                        "partie_id": pm["partie_id"],
                        "titre": pm["titre"],
                        "taggedText": pm["original_text"],
                    }
                    for pm in partMeta
                ],
                "metadata": {"voiceTags": 0, "soundTags": 0, "error": str(e)},
            }

    # ==================================================================
    # Prompt builder for tagging
    # ==================================================================

    def _buildTaggingPrompt(
        self,
        narrationText: str,
        ton: str,
        voiceInstructions: str,
        notesProduction: str,
    ) -> str:
        """Build the LLM prompt for inserting ElevenLabs / sound tags."""
        sections: List[str] = [
            "Voici un scénario audio complet. Insérez les balises vocales "
            "ElevenLabs [] et les marqueurs de sons d'ambiance {} aux "
            "endroits appropriés.\n",
        ]

        if ton:
            sections.append(f"TON GÉNÉRAL DU SCÉNARIO : {ton}\n")

        if voiceInstructions:
            sections.append(
                f"CONSIGNES VOCALES DE L'UTILISATEUR :\n{voiceInstructions}\n"
            )

        if notesProduction:
            sections.append(
                f"NOTES DE PRODUCTION :\n{notesProduction}\n"
            )

        sections.append(
            "RÈGLES DE BALISAGE :\n"
            "1. Balises vocales [] : insérez-les DANS le texte pour guider "
            "la voix. Exemples :\n"
            "   [pause 2s], [rire], [murmure], [ton grave], [soupir], "
            "[voix forte], [chuchotement], [stupeur], [hésitation], "
            "[émotion contenue], [acceleration], [ralentissement]\n"
            "2. Marqueurs sons {} : insérez-les en début de paragraphe ou "
            "aux transitions. Nommez-les en snake_case.wav.\n"
            "   Exemples : {ambiance_port_brume.wav}, {foule_agitee.wav}, "
            "{clapotis_eau.wav}\n"
            "3. NE modifiez PAS le texte narratif — ajoutez uniquement des "
            "balises.\n"
            "4. Conservez les marqueurs === PARTIE N : Titre === pour que "
            "je puisse re-séparer les parties.\n"
            "5. Soyez subtil : maximum 2-3 balises vocales par paragraphe, "
            "1-2 sons d'ambiance par partie.\n"
            "6. Adaptez les balises au ton de chaque partie.\n\n"
        )

        sections.append("TEXTE À BALISER :\n\n" + narrationText)

        sections.append(
            "\n\nRetournez UNIQUEMENT le texte balisé (pas de JSON, pas de "
            "commentaires, pas de markdown). Commencez directement par le texte."
        )

        return "\n".join(sections)

    # ==================================================================
    # Helpers
    # ==================================================================

    def _splitTaggedTextByParts(
        self, taggedText: str, partMeta: List[Dict]
    ) -> List[Dict]:
        """Split a tagged text back into per-part sections using
        ``=== PARTIE N`` markers."""
        # Try to split on the markers
        parts: List[Dict] = []
        pattern = r"===\s*PARTIE\s+(\d+)\s*.*?==="
        splits = re.split(pattern, taggedText)

        if len(splits) <= 1:
            # No markers found – return as single block
            return [
                {
                    "partie_id": pm["partie_id"],
                    "titre": pm["titre"],
                    "taggedText": taggedText if i == 0 else "",
                }
                for i, pm in enumerate(partMeta)
            ]

        # splits looks like: [preamble, "1", text1, "2", text2, ...]
        idx = 1  # skip preamble
        while idx < len(splits) - 1:
            partNum = splits[idx].strip()
            partText = splits[idx + 1].strip()
            # Remove leading metadata lines (ton, ambiances)
            cleanedText = self._cleanPartHeader(partText)
            # Find matching meta
            meta = next(
                (m for m in partMeta if str(m["partie_id"]) == partNum),
                {"partie_id": partNum, "titre": ""},
            )
            parts.append(
                {
                    "partie_id": meta["partie_id"],
                    "titre": meta.get("titre", ""),
                    "taggedText": cleanedText,
                }
            )
            idx += 2

        return parts

    def _cleanPartHeader(self, text: str) -> str:
        """Remove the metadata header lines (ton, ambiances, moments)
        that were injected before the actual narration."""
        lines = text.split("\n")
        cleaned: List[str] = []
        headerDone = False
        for line in lines:
            if not headerDone:
                stripped = line.strip()
                if (
                    stripped.startswith("[ton:")
                    or stripped.startswith("Ambiances suggérées:")
                    or stripped.startswith("Moments clés:")
                    or stripped == ""
                ):
                    continue
                headerDone = True
            cleaned.append(line)
        return "\n".join(cleaned)

    def _countTags(self, text: str, pattern: str) -> int:
        return len(re.findall(pattern, text))

    # ==================================================================
    # Legacy methods (kept for backward compat)
    # ==================================================================

    def create_audio_timeline(
        self,
        scenario: Dict[str, Any],
        sound_library: Optional[Dict] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Legacy: create audio timeline. Kept for backward compat."""
        logger.warning(
            "create_audio_timeline is deprecated — use formatWithTags instead"
        )
        from datetime import datetime

        timeline_id = f"scenario_{scenario.get('scenario_id')}_timeline_v1"
        tracks: Dict[str, List] = {
            "narration_track": [],
            "archives_track": [],
            "ambiances_track": [],
            "sfx_track": [],
            "music_track": [],
        }
        current_time = 0.0

        for part in scenario.get("parties", []):
            if not isinstance(part, dict):
                continue
            narr = self._create_narration_region(part, current_time, config)
            tracks["narration_track"].append(narr)
            for mc in part.get("moments_cles", []):
                if not isinstance(mc, dict):
                    continue
                if mc.get("action") == "archive_audio":
                    ar = self._create_archive_region(mc, current_time, part)
                    if ar:
                        tracks["archives_track"].append(ar)
            for amb in part.get("ambiances_continues", []):
                if not isinstance(amb, dict):
                    continue
                ar = self._create_ambiance_region(amb, current_time, part)
                if ar:
                    tracks["ambiances_track"].append(ar)
            current_time += part.get("duree", 0)

        return {
            "timeline_id": timeline_id,
            "scenario_id": scenario.get("scenario_id"),
            "duree_totale": current_time,
            "tracks": tracks,
            "transitions": [],
            "master_parameters": self._calculate_master_parameters(config),
            "metadata": {
                "total_regions": sum(len(r) for r in tracks.values()),
                "generation_timestamp": datetime.now().isoformat(),
            },
            "quality_checks": {},
        }

    # -- Legacy region helpers --

    def _create_narration_region(self, part, start, config):
        pid = part.get("partie_id", 1)
        dur = part.get("duree", 0)
        tone = part.get("ton", {})
        if not isinstance(tone, dict):
            tone = {"global": str(tone), "tempo_lecture": 110, "pauses": []}
        return {
            "id": f"narr_{pid:02d}",
            "start_time": start,
            "end_time": start + dur,
            "duration": dur,
            "text_file": f"scenario_part_{pid}_narration.txt",
            "estimated_words": len(
                re.findall(r"\b\w+\b", part.get("texte_narration", ""))
            ),
            "tempo_lecture": tone.get("tempo_lecture", 110),
            "tone": tone.get("global", "neutral"),
            "volume": 0.8,
            "effects": [],
            "pauses": tone.get("pauses", []),
        }

    def _create_archive_region(self, moment, part_start, part):
        ts = moment.get("timestamp", "0:00")
        offset = self._parse_timestamp(ts)
        seg = moment.get("segment", {})
        dur = seg.get("end", 0) - seg.get("start", 0)
        if dur <= 0:
            return None
        return {
            "id": f"arch_{part.get('partie_id', 0):02d}",
            "start_time": part_start + offset,
            "end_time": part_start + offset + dur,
            "duration": dur,
            "source_file": moment.get("fichier", ""),
            "volume": moment.get("volume", 0.7),
            "fade_in": moment.get("fade_in", 1.0),
            "fade_out": moment.get("fade_out", 1.0),
        }

    def _create_ambiance_region(self, amb, part_start, part):
        s = self._parse_timestamp(amb.get("start", "0:00"))
        e = self._parse_timestamp(amb.get("end", "0:00"))
        dur = e - s
        if dur <= 0:
            return None
        return {
            "id": f"amb_{part.get('partie_id', 0):02d}",
            "start_time": part_start + s,
            "end_time": part_start + e,
            "duration": dur,
            "file": amb.get("son", ""),
            "volume": amb.get("volume", 0.3),
        }

    def _calculate_master_parameters(self, config):
        specs = (
            config.get("scenario_config", {}).get("audio_specifications", {})
            if config
            else {}
        )
        return {
            "target_loudness": specs.get("loudness_target", -16.0),
            "dynamic_range": specs.get("dynamic_range", "moderate"),
        }

    def _parse_timestamp(self, ts) -> float:
        if isinstance(ts, (int, float)):
            return float(ts)
        if not isinstance(ts, str):
            return 0.0
        try:
            if ":" in ts:
                parts = ts.split(":")
                if len(parts) == 2:
                    return int(parts[0]) * 60 + float(parts[1])
                if len(parts) == 3:
                    return (
                        int(parts[0]) * 3600
                        + int(parts[1]) * 60
                        + float(parts[2])
                    )
            return float(ts)
        except (ValueError, TypeError):
            return 0.0
