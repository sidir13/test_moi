"""
Script rapide pour vérifier la configuration Ollama.
"""

import sys

def check_ollama():
    """Vérifie qu'Ollama est prêt."""
    try:
        import requests
    except ImportError:
        print("❌ Module 'requests' manquant")
        print("   Installez avec: pip install requests")
        return False
    
    url = "http://localhost:11434"
    
    # Test connexion
    try:
        response = requests.get(f"{url}/api/tags", timeout=3)
        if response.status_code != 200:
            print(f"❌ Ollama répond mais statut: {response.status_code}")
            return False
        
        # Liste des modèles
        data = response.json()
        models = data.get('models', [])
        
        if not models:
            print("⚠️  Ollama connecté mais aucun modèle installé")
            print("\n💡 Téléchargez un modèle:")
            print("   ollama pull qwen2.5:latest")
            return False
        
        print("✅ Ollama est prêt !")
        print(f"\n📦 Modèles disponibles ({len(models)}):")
        for model in models:
            name = model.get('name', 'unknown')
            size_gb = model.get('size', 0) / (1024**3)
            print(f"   • {name} ({size_gb:.1f} GB)")
        
        # Vérifier qwen2.5
        model_names = [m.get('name', '') for m in models]
        if 'qwen2.5:latest' in model_names:
            print("\n✅ Modèle recommandé (qwen2.5:latest) installé")
        else:
            print("\n💡 Pour de meilleurs résultats en français, installez:")
            print("   ollama pull qwen2.5:latest")
        
        print("\n🚀 Vous pouvez maintenant lancer:")
        print("   python main_local.py")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Impossible de se connecter à Ollama")
        print("\n💡 Solutions:")
        print("   1. Vérifiez qu'Ollama est installé (https://ollama.ai)")
        print("   2. Lancez Ollama: ollama serve")
        print("   3. Vérifiez l'URL: http://localhost:11434")
        return False
    
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


if __name__ == '__main__':
    print("🔍 Vérification de la configuration Ollama...\n")
    
    if check_ollama():
        sys.exit(0)
    else:
        sys.exit(1)
