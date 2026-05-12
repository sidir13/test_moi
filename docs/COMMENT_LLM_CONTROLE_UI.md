# Comment le LLM contrôle l'interface web

> Explication technique de la connexion entre Claude (IA) et le frontend React

---

## Exemple concret : "corrige les fautes dans le textarea"

> L'utilisateur a tapé **"tu parle pa le francais"** dans le textarea.  
> Il envoie dans le chat : **"corrige les fautes"**

Les deux colonnes se déroulent en parallèle — gauche = ce que tu vois, droite = ce qui se passe dans le code.

| Ce que tu vois dans le navigateur | Ce qui se passe dans le code |
|-----------------------------------|------------------------------|
| Tu cliques sur Envoyer | `ChatPanel.tsx` lit `window.__projectNotes = "tu parle pa le francais"` |
| — | `ws.send({ text: "corrige les fautes", project_notes: "tu parle pa le francais" })` → envoi WebSocket |
| — | `app.py` reçoit le payload, extrait `frontend_notes = "tu parle pa le francais"` |
| — | `chat_agent.py` construit le message pour Claude : `"[projet: "992i"] corrige les fautes [...] [Contexte narratif actuel du projet (textarea) : tu parle pa le francais]"` |
| Un indicateur "en cours…" apparaît | `chat_agent.py` appelle `client.messages.create(...)` → API Anthropic |
| — | Claude lit le message, voit le bloc `[Contexte narratif...]`, décide d'appeler `update_project_notes` |
| Dans le chat : `⚙ update_project_notes` | Backend reçoit `stop_reason = "tool_use"`, envoie `{"type": "tool_call", "tool": "update_project_notes"}` via WebSocket |
| — | `execute_tool("update_project_notes", {"project_name": "992i", "description": "Tu ne parles pas le français."})` |
| — | La fonction Python écrit dans `data/projects/992i/config.json` : `"project_notes": "Tu ne parles pas le français."` |
| — | Backend envoie `{"type": "tool_result", "tool": "update_project_notes", "result": "{\"project_notes\": \"Tu ne parles pas le français.\"}"}` |
| **Le textarea passe à "Tu ne parles pas le français."** | `ChatPanel.tsx` reçoit le `tool_result`, dispatch `CustomEvent("project-notes-updated", { text: "Tu ne parles pas le français." })` |
| — | `ProjectDetailsView.tsx` écoute l'événement → `setNotes("Tu ne parles pas le français.")` → re-render React |
| — | Claude reprend, génère sa réponse texte finale |
| Dans le chat : `"J'ai corrigé le texte."` | Backend envoie `{"type": "assistant_text", "text": "J'ai corrigé le texte."}` |
| — | `{"type": "done"}` → WebSocket reste ouvert pour le prochain message |

---

## Vue d'ensemble

```
Utilisateur tape dans le chat
         │
         ▼
  [Frontend React]
  ChatPanel.tsx
  envoie via WebSocket
         │
         ▼
  [Backend FastAPI]
  app.py → chat_agent.py
  appelle l'API Claude
         │
         ▼
  [Claude (LLM)]
  décide d'appeler un "tool"
  ex: update_project_notes
         │
         ▼
  [Backend exécute le tool]
  main.py → Python function
  modifie config.json
         │
         ▼
  [Backend renvoie le résultat]
  via WebSocket → tool_result
         │
         ▼
  [Frontend réagit]
  ChatPanel.tsx écoute le résultat
  dispatch un CustomEvent
         │
         ▼
  [La vue concernée écoute l'événement]
  ProjectDetailsView.tsx
  met à jour le textarea dans le DOM
```

---

## Étape 1 — L'utilisateur envoie un message

Dans `app/src/components/ChatPanel.tsx`, quand l'utilisateur clique sur Envoyer :

```typescript
const currentNotes = window.__projectNotes; // contenu actuel du textarea
ws.send(JSON.stringify({
  text: message,
  project_notes: currentNotes || undefined  // ← on envoie aussi ce qu'il y a dans le textarea
}));
```

Le message part en **WebSocket** (connexion permanente bidirectionnelle, plus rapide qu'une requête HTTP classique).

---

## Étape 2 — Le backend reçoit et prépare le message

Dans `src/server/app.py`, le WebSocket handler lit le payload :

```python
@app.websocket("/ws/chat")
async def websocket_chat(websocket, session_id):
    payload = json.loads(data)
    text = payload.get("text", "")
    frontend_notes = payload.get("project_notes") or None  # ← contenu du textarea
    await chat_agent.handle_message(session_id, text, session_store, websocket,
                                    frontend_notes=frontend_notes)
```

---

## Étape 3 — chat_agent.py injecte le contexte et appelle Claude

Dans `src/server/chat_agent.py` :

```python
# 1. On injecte le contenu du textarea dans le message
if frontend_notes:
    project_notes_context = f"\n\n[Contexte narratif actuel du projet (textarea) :\n{frontend_notes}\n]"

# 2. Le message final envoyé à Claude ressemble à :
# "[projet: "992i"] Corrige les erreurs
#  [Contexte session : projet actif = "992i", session_id = abc]
#  [Contexte narratif actuel du projet (textarea) :
#  tu parle pa le francais
#  ]"

# 3. On appelle l'API Claude avec la liste des tools disponibles
response = client.messages.create(
    model="anthropic/claude-sonnet-4-20250514",
    tools=TOOLS,          # ← liste de ce que Claude peut faire
    system="...",         # ← instructions de comportement
    messages=messages,
)
```

Claude voit donc exactement ce que l'utilisateur a tapé dans le textarea, en temps réel.

---

## Étape 4 — Claude décide d'appeler un "tool"

Un **tool** (outil) est une fonction Python que Claude peut demander à exécuter.  
La liste est définie dans `main.py` :

```python
TOOLS = [
    {
        "name": "update_project_notes",
        "description": "Mettre à jour le champ 'Contexte narratif' du projet...",
        "input_schema": {
            "properties": {
                "project_name": {"type": "string"},
                "description": {"type": "string"}   # ← le nouveau texte à écrire
            }
        }
    },
    {
        "name": "select_voice",
        ...
    },
    {
        "name": "transcribe_audio",
        ...
    },
    # etc.
]
```

Claude répond avec `stop_reason = "tool_use"` et indique quel tool appeler et avec quels arguments.  
**Claude ne peut pas directement modifier l'interface** — il demande au backend de le faire.

---

## Étape 5 — Le backend exécute le tool

Dans `chat_agent.py`, quand Claude répond avec `tool_use` :

```python
if response.stop_reason == "tool_use":
    for block in response.content:
        if block.type == "tool_use":
            # Envoyer au frontend : "je suis en train d'utiliser cet outil"
            await websocket.send_json({
                "type": "tool_call",
                "tool": block.name,         # ex: "update_project_notes"
                "input": block.input,
            })

            # Exécuter la fonction Python correspondante
            result = execute_tool(block.name, block.input)
            # → appelle update_project_notes(project_name="992i", description="Tu ne parles pas le français")

            # Renvoyer le résultat au frontend
            await websocket.send_json({
                "type": "tool_result",
                "tool": block.name,
                "result": result,           # ex: {"project_notes": "Tu ne parles pas le français"}
            })
```

La fonction `execute_tool` dans `main.py` appelle la vraie fonction Python :

```python
elif tool_name == "update_project_notes":
    return update_project_notes(
        project_name=inputs.get("project_name"),
        description=inputs.get("description"),
    )
```

Cette fonction écrit dans `data/projects/<nom>/config.json`.

---

## Étape 6 — Le frontend réagit au résultat

Dans `ChatPanel.tsx`, le `socket.onmessage` écoute tous les messages WebSocket :

```typescript
socket.onmessage = (event) => {
  const payload = JSON.parse(event.data);

  if (payload.type === "tool_result" && payload.tool === "update_project_notes") {
    const updatedText = JSON.parse(payload.result).project_notes;

    // Émettre un événement personnalisé dans le navigateur
    window.dispatchEvent(new CustomEvent("project-notes-updated", {
      detail: { text: updatedText }
    }));
  }

  if (payload.tool === "select_voice") {
    window.dispatchEvent(new CustomEvent("voice-selected", {
      detail: { voice_id: "...", voice_label: "Voix 1" }
    }));
  }

  if (payload.tool === "auto_select_audio") {
    window.dispatchEvent(new Event("audio-selection-updated"));
  }
};
```

---

## Étape 7 — La vue écoute l'événement et met à jour l'UI

Dans `ProjectDetailsView.tsx` :

```typescript
useEffect(() => {
  const handler = (e: Event) => {
    const text = (e as CustomEvent).detail.text;
    setNotes(text);                     // ← met à jour le state React → le textarea s'actualise
    window.__projectNotes = text;       // ← garde une copie globale pour le prochain envoi
  };

  window.addEventListener("project-notes-updated", handler);
  return () => window.removeEventListener("project-notes-updated", handler);
}, []);
```

Le `setNotes(text)` déclenche un re-render React → le `<textarea>` affiche le nouveau texte.

---

## La boucle complète résumée

| Qui | Quoi | Comment |
|-----|------|---------|
| Utilisateur | Tape dans le chat | Formulaire React |
| ChatPanel.tsx | Envoie le message + contenu textarea | WebSocket JSON |
| app.py | Reçoit, extrait `project_notes` | WebSocket handler |
| chat_agent.py | Injecte contexte, appelle Claude | API Anthropic |
| Claude | Décide d'un tool à appeler | Réponse `tool_use` |
| chat_agent.py | Exécute le tool Python | `execute_tool()` |
| Fonction Python | Modifie le fichier `config.json` | Lecture/écriture JSON |
| chat_agent.py | Renvoie le résultat | WebSocket JSON |
| ChatPanel.tsx | Reçoit `tool_result` | `onmessage` handler |
| ChatPanel.tsx | Émet un CustomEvent | `window.dispatchEvent` |
| Vue React | Écoute l'événement, met à jour l'état | `addEventListener` + `setState` |
| DOM | Le textarea / bouton se met à jour | Re-render React |

---

## Pourquoi le textarea envoyait une vieille valeur ?

Le problème qu'on a corrigé : il existait un tool `get_project_notes` qui lisait `config.json`.  
Claude l'appelait avant de répondre, récupérait une ancienne valeur, et ignorait ce que l'utilisateur venait de taper.

**La fix** : supprimer ce tool de la liste `TOOLS`. Claude ne peut plus le demander — il est forcé de lire le contenu injecté automatiquement dans chaque message (le `window.__projectNotes` envoyé depuis le frontend).

---

## Les autres tools qui contrôlent l'UI

| Tool | Effet dans l'interface |
|------|----------------------|
| `update_project_notes` | Met à jour le textarea "Contexte narratif" |
| `select_voice` | Sélectionne un bouton radio de voix |
| `auto_select_audio` | Coche/décoche des fichiers audio |
| `select_audio_manually` | Sélectionne des ambiances sonores |
| `transcribe_audio` | Lance la transcription, met à jour la vue |
| `generate_historical_scenario` | Lance le pipeline de génération de scénarios |
