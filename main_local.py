"""
Main local pour tester l'architecture avec Ollama ou Groq.

Usage:
    # Mode interactif (demande votre prompt au lancement)
    python main_local.py
    python main_local.py --provider groq
    
    # Avec prompt en argument
    python main_local.py "Votre demande ici"
    python main_local.py --provider groq "Votre demande ici"
    python main_local.py --provider groq --model llama-3.1-70b "Votre demande"
    
    # Exemple complet
    python main_local.py "Un documentaire de 5 minutes sur la grève des mineurs de 1948"

Configuration:
    - Provider par défaut : ollama
    - Ollama : qwen3:8b (par défaut)
    - Groq : llama-3.1-8b (par défaut)
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Configuration Ollama
OLLAMA_CONFIG = {
    'model': 'qwen3:8b',  # ou 'llama3:latest', 'mistral:latest', etc.
    'base_url': 'http://localhost:11434',
    'timeout': 600  # Timeout en secondes pour les requêtes (10 minutes)
}

# Configuration Groq
GROQ_CONFIG = {
    'model': 'llama-3.1-8b',  # ou 'llama-3.1-70b', 'mixtral-8x7b', etc.
    'timeout': 300  # Timeout en secondes (5 minutes)
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_ollama_connection():
    """Vérifie que Ollama est accessible."""
    try:
        import requests
        response = requests.get(f"{OLLAMA_CONFIG['base_url']}/api/tags", timeout=30)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            logger.info(f"✓ Ollama connecté. Modèles disponibles: {model_names}")
            
            # Vérifier si le modèle configuré existe
            if OLLAMA_CONFIG['model'] not in model_names:
                logger.warning(f"⚠ Modèle {OLLAMA_CONFIG['model']} non trouvé. Téléchargez-le avec:")
                logger.warning(f"   ollama pull {OLLAMA_CONFIG['model']}")
                return False
            return True
        else:
            logger.error(f"✗ Ollama répond mais statut: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"✗ Impossible de se connecter à Ollama: {e}")
        logger.error("Assurez-vous que Ollama est lancé : ollama serve")
        return False


def create_local_orchestrator():
    """Crée un orchestrateur configuré pour Ollama."""
    from utils.ollama_client import OllamaClientWrapper
    from utils.logger import setup_logger, AgentLogger
    from utils.skill_loader import SkillLoader
    
    logger.info("=" * 80)
    logger.info("Initialisation de l'orchestrateur LOCAL (Ollama)")
    logger.info("=" * 80)
    
    # Create Ollama client
    ollama_client = OllamaClientWrapper(
        model=OLLAMA_CONFIG['model'],
        base_url=OLLAMA_CONFIG['base_url'],
        timeout=OLLAMA_CONFIG.get('timeout', 600)
    )
    
    # Load default config
    config_path = Path("config/default_config.json")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            default_config = json.load(f)
        logger.info(f"✓ Configuration chargée depuis {config_path}")
    else:
        logger.warning("⚠ Configuration par défaut non trouvée")
        default_config = {}
    
    # Load agents and skills
    agents = {}
    skills = {}
    
    logger.info("Chargement des agents avec Ollama...")
    agents_dir = Path("agents")
    if agents_dir.exists():
        agents = SkillLoader.load_all_skills(
            agents_dir,
            ollama_client.client,
            skill_type="agents"
        )
        logger.info(f"✓ {len(agents)} agents chargés")
    
    logger.info("Chargement des skills avec Ollama...")
    skills_dir = Path("skills")
    if skills_dir.exists():
        skills = SkillLoader.load_all_skills(
            skills_dir,
            ollama_client.client,
            skill_type="skills"
        )
        logger.info(f"✓ {len(skills)} skills chargés")
    
    return {
        'client': ollama_client,
        'agents': agents,
        'skills': skills,
        'default_config': default_config
    }


def run_agent_0_test(orchestrator, user_prompt=None):
    """Test Agent 0 avec Ollama."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST AGENT 0 : Request Parser")
    logger.info("=" * 80)
    
    if 'agent_0_request_parser' not in orchestrator['agents']:
        logger.error("✗ Agent 0 non chargé")
        return None
    
    agent_0 = orchestrator['agents']['agent_0_request_parser']['instance']
    
    # Utiliser le prompt fourni ou demander à l'utilisateur
    if user_prompt:
        prompt = user_prompt
    else:
        default_prompt = "Un documentaire de 3 minutes sur une grève de dockers en 1905"
        print("\n" + "-" * 80)
        print("🎤 ENTREZ VOTRE DEMANDE")
        print("-" * 80)
        print(f"Exemple : {default_prompt}")
        print("\nAppuyez sur Enter pour utiliser l'exemple ci-dessus")
        print("ou tapez votre propre demande :")
        print("-" * 80)
        prompt = input("\n> ").strip()
        
        if not prompt:
            prompt = default_prompt
            logger.info("Utilisation du prompt par défaut")
    
    logger.info(f"\n📝 Prompt: \"{prompt}\"")
    
    try:
        logger.info("Parsing en cours...")
        config = agent_0.parse(prompt, "simple", orchestrator['default_config'])
        
        logger.info("✓ Agent 0 a terminé avec succès")
        
        # Générer résumé
        summary = agent_0.generate_summary(config)
        logger.info(f"\nRésumé généré:\n{summary}")
        
        # Validation
        validation = agent_0.validate_configuration(config)
        logger.info(f"\nValidation: {'✓ OK' if validation['valid'] else '✗ Erreurs'}")
        
        if validation['warnings']:
            logger.warning("Avertissements:")
            for warning in validation['warnings']:
                logger.warning(f"  - {warning}")
        
        return config
        
    except Exception as e:
        logger.error(f"✗ Erreur Agent 0: {e}", exc_info=True)
        return None


def run_agent_1_test(orchestrator, config):
    """Test Agent 1 avec Ollama."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST AGENT 1 : Narrative Structure Architect")
    logger.info("=" * 80)
    
    if 'agent_1_structure' not in orchestrator['agents']:
        logger.error("✗ Agent 1 non chargé")
        return None
    
    agent_1 = orchestrator['agents']['agent_1_structure']['instance']
    
    try:
        logger.info("Création de la structure narrative...")
        structure = agent_1.create_narrative_structure(config, 1)
        
        logger.info("✓ Agent 1 a terminé avec succès")
        logger.info(f"\nTitre: {structure.get('titre_global', 'N/A')}")
        logger.info(f"Durée totale: {structure.get('duree_totale', 0)}s")
        logger.info(f"Nombre de parties: {len(structure.get('structure', []))}")
        
        for part in structure.get('structure', []):
            logger.info(f"  Partie {part['partie']}: {part['titre']} ({part['duree_cible']}s)")
        
        return structure
        
    except Exception as e:
        logger.error(f"✗ Erreur Agent 1: {e}", exc_info=True)
        return None


def run_agent_2_test(orchestrator, structure, config):
    """Test Agent 2 avec Ollama."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST AGENT 2 : Historical Scenario Writer")
    logger.info("=" * 80)
    
    if 'agent_2_writing' not in orchestrator['agents']:
        logger.error("✗ Agent 2 non chargé")
        return None
    
    agent_2 = orchestrator['agents']['agent_2_writing']['instance']
    
    # Inject skills
    agent_2.set_skills(orchestrator['skills'])
    
    try:
        logger.info("Écriture du scénario...")
        scenario = agent_2.write_complete_scenario(structure, config)
        
        logger.info("✓ Agent 2 a terminé avec succès")
        logger.info(f"\nTitre: {scenario.get('titre', 'N/A')}")
        logger.info(f"Nombre de mots: {scenario.get('metadata', {}).get('nombre_mots', 0)}")
        logger.info(f"Durée estimée: {scenario.get('duree_estimee', 0):.1f}s")
        
        # Afficher extrait de narration
        if scenario.get('parties'):
            first_part = scenario['parties'][0]
            texte = first_part.get('texte_narration', '')
            logger.info(f"\nExtrait (partie 1):")
            logger.info(f"  {texte[:200]}...")
        
        return scenario
        
    except Exception as e:
        logger.error(f"✗ Erreur Agent 2: {e}", exc_info=True)
        return None


def run_agent_3_test(orchestrator, scenario, config):
    """Test Agent 3 avec Ollama."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST AGENT 3 : Audio Production Engineer")
    logger.info("=" * 80)
    
    if 'agent_3_production' not in orchestrator['agents']:
        logger.error("✗ Agent 3 non chargé")
        return None
    
    agent_3 = orchestrator['agents']['agent_3_production']['instance']
    
    # Inject skills
    agent_3.set_skills(orchestrator['skills'])
    
    try:
        logger.info("Création de la timeline audio...")
        timeline = agent_3.create_audio_timeline(scenario, None, config)
        
        logger.info("✓ Agent 3 a terminé avec succès")
        logger.info(f"\nTimeline ID: {timeline.get('timeline_id', 'N/A')}")
        logger.info(f"Durée totale: {timeline.get('duree_totale', 0):.1f}s")
        logger.info(f"Nombre de tracks: {len(timeline.get('tracks', {}))}")
        
        for track_name, regions in timeline.get('tracks', {}).items():
            if regions:
                logger.info(f"  {track_name}: {len(regions)} régions")
        
        return timeline
        
    except Exception as e:
        logger.error(f"✗ Erreur Agent 3: {e}", exc_info=True)
        return None


def save_local_outputs(config, structure, scenario, timeline):
    """Sauvegarde les résultats des tests."""
    output_dir = Path("output/local_tests")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Sauvegarder config
    if config:
        config_file = output_dir / f"config_{timestamp}.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Config sauvegardée: {config_file}")
    
    # Sauvegarder structure
    if structure:
        structure_file = output_dir / f"structure_{timestamp}.json"
        with open(structure_file, 'w', encoding='utf-8') as f:
            json.dump(structure, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Structure sauvegardée: {structure_file}")
    
    # Sauvegarder scénario
    if scenario:
        scenario_file = output_dir / f"scenario_{timestamp}.json"
        with open(scenario_file, 'w', encoding='utf-8') as f:
            json.dump(scenario, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Scénario sauvegardé: {scenario_file}")
    
    # Sauvegarder timeline
    if timeline:
        timeline_file = output_dir / f"timeline_{timestamp}.json"
        with open(timeline_file, 'w', encoding='utf-8') as f:
            json.dump(timeline, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Timeline sauvegardée: {timeline_file}")


def main():
    """Main function pour tests locaux avec Ollama ou Groq."""
    # Parser les arguments
    parser = argparse.ArgumentParser(
        description="Test local de l'architecture avec Ollama ou Groq"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Prompt pour générer le scénario (optionnel, mode interactif sinon)"
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "groq"],
        default="ollama",
        help="Provider à utiliser (ollama ou groq)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Modèle spécifique à utiliser"
    )
    
    args = parser.parse_args()
    
    # Configuration selon le provider
    if args.provider == "groq":
        provider_name = "Groq"
        model = args.model or GROQ_CONFIG['model']
        timeout = GROQ_CONFIG['timeout']
    else:
        provider_name = "Ollama"
        model = args.model or OLLAMA_CONFIG['model']
        timeout = OLLAMA_CONFIG['timeout']
    
    print("\n" + "=" * 80)
    print(f"🎙️  MÉMOIRE DES TERRITOIRES - Tests Locaux avec {provider_name}")
    print("=" * 80)
    print(f"\nProvider: {provider_name}")
    print(f"Modèle: {model}")
    print(f"Timeout: {timeout}s\n")
    
    # Récupérer le prompt
    user_prompt = args.prompt
    if user_prompt:
        logger.info(f"Prompt fourni: \"{user_prompt}\"")
    
    # 1. Vérifier la connexion
    logger.info(f"Étape 1: Vérification de la connexion {provider_name}")
    if args.provider == "ollama":
        if not check_ollama_connection():
            logger.error("\n❌ Impossible de continuer sans Ollama")
            logger.info("\nPour installer et lancer Ollama:")
            logger.info("  1. Téléchargez depuis https://ollama.ai")
            logger.info("  2. Lancez: ollama serve")
            logger.info(f"  3. Téléchargez un modèle: ollama pull {model}")
            sys.exit(1)
    else:
        # Vérifier Groq
        from utils.groq_client import test_groq_connection
        if not test_groq_connection(model=model):
            logger.error("❌ Connexion Groq échouée. Vérifiez votre GROQ_API_KEY dans .env")
            sys.exit(1)
        logger.info(f"✓ Connexion Groq OK avec {model}")
    
    # 2. Créer orchestrateur
    logger.info(f"\nÉtape 2: Création de l'orchestrateur avec {provider_name}")
    try:
        if args.provider == "groq":
            from utils.groq_client import GroqClientWrapper
            client = GroqClientWrapper(model=model, timeout=timeout)
        else:
            from utils.ollama_client import OllamaClientWrapper
            client = OllamaClientWrapper(
                model=model,
                base_url=OLLAMA_CONFIG['base_url'],
                timeout=timeout
            )
        
        from orchestrator import ScenarioMakerOrchestrator
        orchestrator = ScenarioMakerOrchestrator(
            client=client,
            config_path="config/default_config.json"
        )
        logger.info("✓ Orchestrateur créé avec succès")
    except Exception as e:
        logger.error(f"❌ Erreur création orchestrateur: {e}", exc_info=True)
        sys.exit(1)
    
    # 3. Tests séquentiels
    logger.info("\nÉtape 3: Tests des agents")
    
    # Agent 0
    config = run_agent_0_test(orchestrator, user_prompt)
    if not config:
        logger.error("❌ Test Agent 0 échoué")
        sys.exit(1)
    
    # Agent 1
    structure = run_agent_1_test(orchestrator, config)
    if not structure:
        logger.error("❌ Test Agent 1 échoué")
        sys.exit(1)
    
    # Agent 2
    scenario = run_agent_2_test(orchestrator, structure, config)
    if not scenario:
        logger.error("❌ Test Agent 2 échoué")
        sys.exit(1)
    
    # Agent 3
    timeline = run_agent_3_test(orchestrator, scenario, config)
    if not timeline:
        logger.error("❌ Test Agent 3 échoué")
        sys.exit(1)
    
    # 4. Sauvegarder résultats
    logger.info("\nÉtape 4: Sauvegarde des résultats")
    save_local_outputs(config, structure, scenario, timeline)
    
    # 5. Résumé final
    print("\n" + "=" * 80)
    print("✅ TOUS LES TESTS RÉUSSIS !")
    print("=" * 80)
    print(f"\nRésultats sauvegardés dans: output/local_tests/")
    print(f"\nPipeline complet testé avec {provider_name} - {model}")
    print("\n💡 Le système fonctionne !")
    print("\n" + "-" * 80)
    print("📖 UTILISATION")
    print("-" * 80)
    print("\n1. Mode interactif Ollama :")
    print("   python main_local.py")
    print("\n2. Mode interactif Groq :")
    print("   python main_local.py --provider groq")
    print("\n3. Avec prompt Ollama :")
    print('   python main_local.py "Votre demande ici"')
    print("\n4. Avec prompt Groq :")
    print('   python main_local.py --provider groq "Votre demande ici"')
    print("\n5. Modèle spécifique Groq :")
    print('   python main_local.py --provider groq --model llama-3.1-70b "Votre demande"')
    print("\n6. Pour passer en production avec Claude :")
    print('   python cli.py generate "votre prompt"')
    print("\n" + "=" * 80)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n⚠ Interruption par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Erreur fatale: {e}", exc_info=True)
        sys.exit(1)
