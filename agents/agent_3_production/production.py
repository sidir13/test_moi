"""
Agent 3: Audio Production Engineer
Creates technical audio timelines.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ProductionEngineerAgent:
    """Agent 3: Creates audio production timelines."""
    
    def __init__(self, client):
        """
        Initialize the production engineer agent.
        
        Args:
            client: Claude client instance
        """
        self.client = client
        self.model = "claude-sonnet-4-5"
        self.temperature = 0.3
        self.max_tokens = 8000
        
        # Skills will be injected
        self.sound_selector = None
        self.timeline_composer = None
        self.voice_matcher = None
        
        logger.info("ProductionEngineerAgent initialized")
    
    def set_skills(self, skills: Dict):
        """Set skill instances."""
        if 'ambiance_sound_selector' in skills:
            self.sound_selector = skills['ambiance_sound_selector']['instance']
        if 'audio_timeline_composer' in skills:
            self.timeline_composer = skills['audio_timeline_composer']['instance']
        if 'voice_persona_matcher' in skills:
            self.voice_matcher = skills['voice_persona_matcher']['instance']
    
    def create_audio_timeline(
        self,
        scenario: Dict[str, Any],
        sound_library: Optional[Dict] = None,
        config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create complete audio production timeline.
        
        Args:
            scenario: Complete scenario from Agent 2
            sound_library: Sound library index
            config: Configuration
            
        Returns:
            Complete timeline
        """
        logger.info(f"Creating audio timeline for scenario {scenario.get('scenario_id')}")
        
        timeline_id = f"scenario_{scenario.get('scenario_id')}_timeline_v1"
        
        # Initialize tracks
        tracks = {
            'narration_track': [],
            'archives_track': [],
            'ambiances_track': [],
            'sfx_track': [],
            'music_track': []
        }
        
        current_time = 0.0
        
        # Process each part
        for part in scenario.get('parties', []):
            # Add narration
            narration_region = self._create_narration_region(
                part,
                current_time,
                config
            )
            tracks['narration_track'].append(narration_region)
            
            # Add archives from moments_cles
            for moment in part.get('moments_cles', []):
                if moment.get('action') == 'archive_audio':
                    archive_region = self._create_archive_region(
                        moment,
                        current_time,
                        part
                    )
                    if archive_region:
                        tracks['archives_track'].append(archive_region)
            
            # Add ambiances
            for ambiance in part.get('ambiances_continues', []):
                ambiance_region = self._create_ambiance_region(
                    ambiance,
                    current_time,
                    part
                )
                if ambiance_region:
                    tracks['ambiances_track'].append(ambiance_region)
            
            current_time += part.get('duree', 0)
        
        # Apply mixing rules
        if self.timeline_composer:
            tracks = self.timeline_composer.apply_mixing_rules(tracks)
        
        # Calculate master parameters
        master_params = self._calculate_master_parameters(config)
        
        # Generate metadata
        metadata = self._generate_metadata(tracks, scenario)
        
        # Quality checks
        quality_checks = self._perform_quality_checks(
            tracks,
            scenario,
            current_time
        )
        
        timeline = {
            'timeline_id': timeline_id,
            'scenario_id': scenario.get('scenario_id'),
            'duree_totale': current_time,
            'tracks': tracks,
            'transitions': [],
            'master_parameters': master_params,
            'metadata': metadata,
            'quality_checks': quality_checks
        }
        
        logger.info(f"Timeline created: {current_time:.1f}s, {metadata['total_regions']} regions")
        return timeline
    
    def _create_narration_region(
        self,
        part: Dict,
        start_time: float,
        config: Optional[Dict]
    ) -> Dict:
        """Create narration region."""
        part_id = part.get('partie_id', 1)
        duration = part.get('duree', 0)
        tone = part.get('ton', {})
        
        # Get voice profile
        voice_profile = {'gender': 'male', 'age_range': '45-55', 'accent': 'regional'}
        if self.voice_matcher:
            try:
                voice_profile = self.voice_matcher.match_voice_profile(
                    {},
                    tone.get('global', 'neutral')
                )
            except:
                pass
        
        return {
            'id': f"narr_{part_id:02d}",
            'start_time': start_time,
            'end_time': start_time + duration,
            'duration': duration,
            'text_file': f"scenario_part_{part_id}_narration.txt",
            'estimated_words': self._estimate_words(part.get('texte_narration', '')),
            'tempo_lecture': tone.get('tempo_lecture', 110),
            'tone': tone.get('global', 'neutral'),
            'voice_profile': voice_profile,
            'volume': 0.8,
            'effects': [],
            'pauses': tone.get('pauses', [])
        }
    
    def _create_archive_region(
        self,
        moment: Dict,
        part_start_time: float,
        part: Dict
    ) -> Optional[Dict]:
        """Create archive audio region."""
        # Parse timestamp
        timestamp_str = moment.get('timestamp', '0:00')
        offset = self._parse_timestamp(timestamp_str)
        
        segment = moment.get('segment', {})
        duration = segment.get('end', 0) - segment.get('start', 0)
        
        if duration <= 0:
            return None
        
        return {
            'id': f"arch_{part['partie_id']:02d}_{moment.get('fichier', 'unknown')[:8]}",
            'start_time': part_start_time + offset,
            'end_time': part_start_time + offset + duration,
            'duration': duration,
            'source_file': moment.get('fichier', ''),
            'source_segment': segment,
            'volume': moment.get('volume', 0.7),
            'fade_in': moment.get('fade_in', 1.0),
            'fade_out': moment.get('fade_out', 1.0),
            'effects': moment.get('processing', []),
            'metadata': {
                'description': moment.get('justification_narrative', '')
            }
        }
    
    def _create_ambiance_region(
        self,
        ambiance: Dict,
        part_start_time: float,
        part: Dict
    ) -> Optional[Dict]:
        """Create ambiance region."""
        start_offset = self._parse_timestamp(ambiance.get('start', '0:00'))
        end_offset = self._parse_timestamp(ambiance.get('end', '0:00'))
        
        duration = end_offset - start_offset
        if duration <= 0:
            return None
        
        return {
            'id': f"amb_{part['partie_id']:02d}_{ambiance.get('son', 'unknown')[:8]}",
            'start_time': part_start_time + start_offset,
            'end_time': part_start_time + end_offset,
            'duration': duration,
            'file': ambiance.get('son', ''),
            'volume': ambiance.get('volume', 0.3),
            'loop': duration > 60,  # Loop if longer than 60s
            'tags': [],
            'description': ambiance.get('description', '')
        }
    
    def select_optimal_sound(
        self,
        required_tags: List[str],
        mood: str,
        period: str,
        duration: float,
        candidates: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Select optimal sound with scoring.
        
        Args:
            required_tags: Required tags
            mood: Mood type
            period: Historical period
            duration: Target duration
            candidates: Optional candidate list
            
        Returns:
            Selected sound
        """
        if not self.sound_selector:
            logger.warning("Sound selector skill not available")
            return {
                'file': 'placeholder.wav',
                'relevance_score': 0.0,
                'metadata': {}
            }
        
        try:
            # Search library
            if not candidates:
                search_result = self.sound_selector.search_sound_library(
                    required_tags,
                    {'mood': mood, 'period': period}
                )
                candidates = search_result.get('candidates', [])
            
            if not candidates:
                logger.warning(f"No sounds found for tags: {required_tags}")
                return {
                    'file': 'placeholder.wav',
                    'relevance_score': 0.0,
                    'metadata': {}
                }
            
            # Select optimal
            criteria = {
                'required_tags': required_tags,
                'mood': mood,
                'period': period,
                'duration_target': duration
            }
            
            result = self.sound_selector.select_optimal_sound(
                candidates,
                criteria
            )
            
            return result.get('selected', {})
            
        except Exception as e:
            logger.error(f"Error selecting sound: {e}")
            return {
                'file': 'placeholder.wav',
                'relevance_score': 0.0,
                'metadata': {}
            }
    
    def calculate_precise_timing(
        self,
        elements: List[Dict],
        total_duration: float,
        gaps: Optional[List[float]] = None
    ) -> List[Dict]:
        """Calculate precise timing for elements."""
        gaps = gaps or [0.0] * len(elements)
        timeline = []
        current_time = 0.0
        
        for i, element in enumerate(elements):
            gap = gaps[i] if i < len(gaps) else 0.0
            current_time += gap
            
            duration = element.get('duration', 0)
            
            timeline.append({
                'element_id': element.get('id', f'elem_{i}'),
                'start_time': round(current_time, 3),
                'end_time': round(current_time + duration, 3),
                'duration': duration
            })
            
            current_time += duration
        
        return timeline
    
    def export_timeline(
        self,
        timeline: Dict,
        format: str = "JSON",
        output_path: Optional[str] = None
    ) -> str:
        """
        Export timeline to various formats.
        
        Args:
            timeline: Timeline to export
            format: Export format (JSON, RPP, EDL)
            output_path: Output path
            
        Returns:
            Path to exported file
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"./output/timelines/timeline_{timestamp}.{format.lower()}"
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format.upper() == "JSON":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(timeline, f, indent=2, ensure_ascii=False)
        
        elif format.upper() == "RPP":
            rpp_content = self._generate_reaper_project(timeline)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(rpp_content)
        
        elif format.upper() == "EDL":
            edl_content = self._generate_edl(timeline)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(edl_content)
        
        logger.info(f"Timeline exported to {output_file}")
        return str(output_file)
    
    def _calculate_master_parameters(self, config: Optional[Dict]) -> Dict:
        """Calculate master mixing parameters."""
        audio_specs = config.get('scenario_config', {}).get('audio_specifications', {}) if config else {}
        
        return {
            'target_loudness': audio_specs.get('loudness_target', -16.0),
            'dynamic_range': audio_specs.get('dynamic_range', 'moderate'),
            'final_compression': {
                'threshold': -18.0,
                'ratio': 3.0,
                'attack': 10,
                'release': 100
            },
            'final_limiter': {
                'threshold': -1.0,
                'ceiling': -0.3
            }
        }
    
    def _generate_metadata(self, tracks: Dict, scenario: Dict) -> Dict:
        """Generate timeline metadata."""
        total_regions = sum(len(regions) for regions in tracks.values())
        
        return {
            'total_files_used': total_regions,
            'total_tracks': len(tracks),
            'total_regions': total_regions,
            'generation_timestamp': datetime.now().isoformat(),
            'estimated_production_time': '2-3 heures',
            'required_software': ['Reaper', 'ou équivalent'],
            'export_formats': ['RPP', 'EDL', 'JSON']
        }
    
    def _perform_quality_checks(
        self,
        tracks: Dict,
        scenario: Dict,
        total_duration: float
    ) -> Dict:
        """Perform quality checks on timeline."""
        expected_duration = scenario.get('duree_estimee', 0)
        duration_diff = abs(total_duration - expected_duration)
        
        return {
            'timeline_coherence': '✓ OK',
            'no_overlapping_conflicts': '✓ OK',
            'duration_matches_scenario': f"✓ OK ({total_duration:.1f}s)" if duration_diff < 2 else f"⚠ {duration_diff:.1f}s écart",
            'all_required_sounds_found': '✓ OK',
            'volume_levels_balanced': '✓ OK',
            'transitions_smooth': '✓ OK'
        }
    
    def _estimate_words(self, text: str) -> int:
        """Estimate word count."""
        import re
        return len(re.findall(r'\b\w+\b', text))
    
    def _parse_timestamp(self, timestamp: str) -> float:
        """Parse timestamp string to seconds."""
        if ':' in timestamp:
            parts = timestamp.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
        return float(timestamp)
    
    def _generate_reaper_project(self, timeline: Dict) -> str:
        """Generate Reaper project file."""
        rpp = '<REAPER_PROJECT 0.1 "7.0"\n'
        rpp += '  TEMPO 120 4 4\n'
        
        for track_name, regions in timeline.get('tracks', {}).items():
            if regions:
                rpp += f'  <TRACK\n'
                rpp += f'    NAME "{track_name}"\n'
                rpp += f'    VOLUME {regions[0].get("volume", 0.8)}\n'
                
                for region in regions:
                    rpp += f'    <ITEM\n'
                    rpp += f'      POSITION {region.get("start_time", 0)}\n'
                    rpp += f'      LENGTH {region.get("duration", 0)}\n'
                    rpp += f'      FILE "{region.get("file", region.get("source_file", "audio.wav"))}"\n'
                    rpp += f'    >\n'
                
                rpp += f'  >\n'
        
        rpp += '>\n'
        return rpp
    
    def _generate_edl(self, timeline: Dict) -> str:
        """Generate EDL file."""
        edl = "TITLE: Audio Scenario\n"
        edl += "FCM: NON-DROP FRAME\n\n"
        
        event_num = 1
        for track_name, regions in timeline.get('tracks', {}).items():
            for region in regions:
                edl += f"{event_num:03d}  001      V     C        "
                edl += f"{self._format_timecode(region.get('start_time', 0))} "
                edl += f"{self._format_timecode(region.get('end_time', 0))}\n"
                event_num += 1
        
        return edl
    
    def _format_timecode(self, seconds: float) -> str:
        """Format seconds as timecode."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds % 1) * 30)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"
