"""
Historical Context Analyzer Skill
Analyzes historical documents and detects anachronisms.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class HistoricalContextAnalyzer:
    """Analyzes historical context and detects anachronisms."""
    
    def __init__(self, client):
        """
        Initialize the analyzer.
        
        Args:
            client: Claude client instance
        """
        self.client = client
        self.model = "claude-sonnet-4-5"
        self.temperature = 0.2
        self.max_tokens = 4000
        
        # Common anachronisms database (simplified)
        self.anachronisms_db = {
            1900: [
                'ordinateur', 'internet', 'télévision', 'radio', 'avion',
                'smartphone', 'digital', 'numérique', 'virtuel', 'en ligne',
                'globalisation', 'mondialisation', 'informatique', 'électronique'
            ],
            1950: [
                'ordinateur personnel', 'internet', 'portable', 'smartphone',
                'numérique', 'digital', 'virtuel', 'en ligne', 'web'
            ]
        }
        
        logger.info("HistoricalContextAnalyzer initialized")
    
    def analyze_historical_documents(
        self,
        documents: List[str],
        period: Dict[str, int],
        location: Optional[str] = None,
        themes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze historical documents to extract enriched context.
        
        Args:
            documents: List of document texts
            period: Period dict with start_year and end_year
            location: Optional location
            themes: Optional themes list
            
        Returns:
            Enriched historical context
        """
        logger.info(f"Analyzing {len(documents)} documents for period {period}")
        
        if not documents:
            logger.warning("No documents provided, returning minimal context")
            return self._minimal_context(period, location, themes)
        
        # Prepare combined document text
        combined_docs = "\n\n---\n\n".join(documents[:5])  # Limit to 5 docs
        
        prompt = f"""Analysez ces documents historiques et extrayez un contexte enrichi.

PÉRIODE : {period.get('start_year')}-{period.get('end_year')}
LIEU : {location or 'Non spécifié'}
THÈMES : {', '.join(themes or [])}

DOCUMENTS :
{combined_docs[:3000]}  # Limit length

MISSION :
1. Identifiez toutes les dates et événements clés mentionnés
2. Listez les personnages importants et leurs rôles
3. Notez les lieux spécifiques
4. Extrayez le vocabulaire d'époque (termes professionnels, expressions, unités)
5. Résumez le contexte social et économique
6. Citez les sources les plus pertinentes
7. Donnez des recommandations pour la narration

Retournez un JSON avec cette structure :
{{
  "contexte_enrichi": {{
    "dates_cles": [{{"date": "YYYY-MM-DD", "evenement": "..."}}],
    "personnages": [{{"nom": "...", "role": "..."}}],
    "lieux_detailles": ["lieu1", "lieu2"],
    "vocabulaire_epoque": {{
      "termes_professionnels": ["terme1", "terme2"],
      "expressions": ["expression1"],
      "unites_mesure": ["unité1"]
    }},
    "contexte_social": "Description...",
    "sources_citees": ["source1", "source2"]
  }},
  "recommendations": ["rec1", "rec2"]
}}

JSON :"""
        
        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            response_text = response.content[0].text
            result = self._extract_json(response_text)
            
            logger.info("Document analysis complete")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing documents: {e}", exc_info=True)
            return self._minimal_context(period, location, themes)
    
    def detect_anachronisms(
        self,
        text: str,
        period_start: int,
        strict_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Detect anachronistic words in text.
        
        Args:
            text: Text to analyze
            period_start: Start year of period
            strict_mode: Use strict detection
            
        Returns:
            Anachronisms detection result
        """
        logger.info(f"Detecting anachronisms for period starting {period_start}")
        
        text_lower = text.lower()
        anachronisms_found = []
        
        # Get relevant anachronisms for period
        relevant_period = min(
            self.anachronisms_db.keys(),
            key=lambda x: abs(x - period_start)
        )
        
        anachronism_list = self.anachronisms_db[relevant_period]
        
        # Simple detection
        for word in anachronism_list:
            if word.lower() in text_lower:
                # Find position
                match = re.search(r'\b' + re.escape(word) + r'\b', text_lower)
                position = match.start() if match else -1
                
                # Determine gravity
                gravity = 'critique' if word in ['ordinateur', 'internet', 'smartphone'] else 'modéré'
                
                anachronisms_found.append({
                    'word': word,
                    'position': position,
                    'gravity': gravity,
                    'reason': f"Terme anachronique pour la période {period_start}",
                    'suggestion': self._suggest_alternative(word, period_start)
                })
        
        # Calculate score
        score = max(0.0, 1.0 - (len(anachronisms_found) * 0.15))
        
        # Verdict
        if score >= 0.9:
            verdict = "excellent"
        elif score >= 0.7:
            verdict = "acceptable_avec_corrections"
        else:
            verdict = "necessite_revision"
        
        result = {
            'anachronisms_found': anachronisms_found,
            'score': score,
            'verdict': verdict,
            'total_anachronisms': len(anachronisms_found)
        }
        
        logger.info(f"Anachronism detection complete: {len(anachronisms_found)} found, score {score:.2f}")
        return result
    
    def extract_period_vocabulary(
        self,
        period: Dict[str, int],
        domain: str,
        sources: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Extract period-specific vocabulary.
        
        Args:
            period: Period dict
            domain: Domain (maritime, industriel, etc.)
            sources: Optional source texts
            
        Returns:
            Vocabulary glossary
        """
        logger.info(f"Extracting vocabulary for {domain} in period {period}")
        
        # Simplified implementation - in real system would use comprehensive database
        vocabulary = {
            'termes_professionnels': [],
            'expressions': [],
            'unites_mesure': []
        }
        
        # Domain-specific vocabulary samples
        if domain == 'maritime':
            vocabulary['termes_professionnels'] = [
                'docker', 'portefaix', 'débardeur', 'matelot', 'capitaine'
            ]
            vocabulary['expressions'] = [
                'faire la belle', 'être à quai', 'charger la cale'
            ]
            vocabulary['unites_mesure'] = [
                'tonneau', 'quintal', 'barrique'
            ]
        elif domain == 'industriel':
            vocabulary['termes_professionnels'] = [
                'ouvrier', 'contremaître', 'machiniste', 'ajusteur'
            ]
            vocabulary['expressions'] = [
                'faire les trois-huit', 'être à la pièce'
            ]
        
        return vocabulary
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from text."""
        import re
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try markdown
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError("Could not extract valid JSON")
    
    def _minimal_context(
        self,
        period: Dict[str, int],
        location: Optional[str],
        themes: Optional[List[str]]
    ) -> Dict:
        """Create minimal context when documents not available."""
        return {
            'contexte_enrichi': {
                'dates_cles': [],
                'personnages': [],
                'lieux_detailles': [location] if location else [],
                'vocabulaire_epoque': {
                    'termes_professionnels': [],
                    'expressions': [],
                    'unites_mesure': []
                },
                'contexte_social': f"Période {period.get('start_year')}-{period.get('end_year')}",
                'sources_citees': []
            },
            'recommendations': ['Enrichir avec des sources historiques spécifiques']
        }
    
    def _suggest_alternative(self, anachronism: str, period: int) -> str:
        """Suggest period-appropriate alternative."""
        alternatives = {
            'ordinateur': 'registre',
            'internet': 'courrier',
            'télévision': 'théâtre',
            'globalisation': 'commerce international',
            'numérique': 'manuscrit',
            'smartphone': 'télégramme'
        }
        
        return alternatives.get(anachronism, 'Reformuler avec vocabulaire d\'époque')
