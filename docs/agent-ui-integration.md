# Comment le chatbot modifie l'interface web en temps réel

## Vue d'ensemble

L'objectif était simple : quand l'utilisateur dit **"sélectionne la voix 1"** dans le chat, la carte "Voix 1" se coche visuellement dans l'interface — sans aucun clic manuel.

Pour y arriver, il a fallu relier trois couches distinctes : le **LLM** (Claude via OpenRouter), le **backend FastAPI** et le **frontend React**.

---

## Architecture du flux

```
Utilisateur (chat)
      │
      │ "sélectionne la voix 1"
      ▼
┌─────────────────┐
│  WebSocket      │  /ws/chat?session_id=...
│  chat_agent.py  │  Boucle agentique : envoie le message à Claude
└────────┬────────┘
         │ Claude répond avec un tool_call : select_voice
         ▼
┌─────────────────┐
│   main.py       │  execute_tool("select_voice", { voice_id, project_name })
│   execute_tool  │  → sauvegarde en base (audio_selection + project profile)
└────────┬────────┘
         │ retourne { status: ok, voice_id, voice_label }
         ▼
┌─────────────────┐
│  chat_agent.py  │  send_json({ type: "tool_result", tool: "select_voice", result: {...} })
└────────┬────────┘
         │ message WebSocket vers le navigateur
         ▼
┌─────────────────┐
│  ChatPanel.tsx  │  reçoit le message WS
│                 │  détecte payload.tool === "select_voice"
│                 │  → window.dispatchEvent(new CustomEvent("voice-selected", { detail }))
└────────┬────────┘
         │ événement DOM
         ▼
┌────────────────────────┐
│  AudioSelectionView.tsx│  écoute "voice-selected"
│                        │  → setSelectedVoiceId(voice_id)  ← mise à jour immédiate
│                        │  → queryClient.invalidateQueries  ← resync en arrière-plan
└────────────────────────┘
```

---

## Les 4 briques techniques

### 1. Le tool `select_voice` (backend — `main.py`)

Claude ne "fait" rien directement. Il émet un **tool_call** structuré que le backend exécute :

```python
# Déclaration du tool dans TOOLS[]
{
    "name": "select_voice",
    "description": "Choisit parmi les 9 voix ElevenLabs prédéfinies. Voix 1=5l4ttmr4SKNgi0HnOelT ...",
    "input_schema": {
        "type": "object",
        "properties": {
            "voice_id":    { "type": "string" },
            "voice_label": { "type": "string" },
            "project_name":{ "type": "string" },
            "reason":      { "type": "string" }
        },
        "required": ["voice_id", "project_name"]
    }
}

# Exécution dans execute_tool()
elif tool_name == "select_voice":
    voice_id = tool_input["voice_id"]
    project_name = tool_input.get("project_name")
    # Sauvegarde dans les deux stores pour cohérence
    current = load_audio_selection(project_name) or {}
    current["tts_voice_id"] = voice_id
    save_audio_selection(project_name, current)           # audio_selection.json
    update_project_config(project_name, {"tts_voice_id": voice_id})  # config.json
    return {"status": "ok", "voice_id": voice_id, "voice_label": ..., "reason": ...}
```

**Piège évité** : le GET `/sessions/{id}/audio-selection` lisait `tts_voice_id` depuis le *project profile* (`config.json`), pas depuis `audio_selection.json`. Il fallait donc écrire dans les deux.

---

### 2. La boucle agentique (`chat_agent.py`)

Le backend transmet chaque étape de l'agent au frontend via WebSocket :

```python
# Quand Claude émet un tool_call
await websocket.send_json({
    "type": "tool_call",
    "tool": block["name"],
    "input": block.get("input", {}),
})

# Après exécution du tool
result = execute_tool(block["name"], block["input"])
await websocket.send_json({
    "type": "tool_result",
    "tool": block["name"],
    "result": json.dumps(result),   # ← sérialisé en string JSON
})
```

---

### 3. L'émission d'événement DOM (`ChatPanel.tsx`)

Le composant chat écoute tous les messages WebSocket. Pour `tool_result`, il dispatche un événement DOM personnalisé :

```typescript
} else if (payload.type === "tool_result") {
    if (payload.tool === "select_voice") {
        const res = typeof payload.result === "string"
            ? JSON.parse(payload.result)
            : payload.result;
        if (res?.voice_id) {
            window.dispatchEvent(new CustomEvent("voice-selected", {
                detail: { voice_id: res.voice_id, voice_label: res.voice_label }
            }));
        }
    }
}
```

Le `CustomEvent` sur `window` permet une communication découplée entre deux composants qui n'ont pas de relation parent/enfant directe dans l'arbre React.

---

### 4. La réaction UI (`AudioSelectionView.tsx`)

La vue audio écoute l'événement et met à jour l'état local **immédiatement** :

```typescript
useEffect(() => {
    const handler = (e: Event) => {
        const { voice_id } = (e as CustomEvent).detail;
        if (voice_id) {
            // Mise à jour visuelle instantanée — pas d'attente réseau
            setSelectedVoiceId(voice_id);
            // Resync du cache React Query en arrière-plan
            queryClient.invalidateQueries({ queryKey: ["audio-selection", sessionId] });
        }
    };
    window.addEventListener("voice-selected", handler);
    return () => window.removeEventListener("voice-selected", handler);
}, [sessionId, queryClient]);
```

L'état `selectedVoiceId` pilote directement la classe CSS de chaque carte voix :

```typescript
const isSelected = selectedVoiceId === voice.id;
// ...
className={cn(
    "rounded-xl border p-3 cursor-pointer transition-all",
    isSelected ? "border-primary bg-primary/5 shadow-sm" : "border-border"
)}
```

---

## Problèmes rencontrés et solutions

### Problème 1 — L'agent demandait "où sont vos fichiers voix ?"

**Cause** : `build_skill_context()` injectait les descriptions des skills (dont `voice_persona_matcher`) dans le premier message utilisateur. Le modèle voyait "matching de profils vocaux avec fichiers" et cherchait des fichiers.

**Solution** : supprimer l'injection de `skill_context` dans le payload. La liste `TOOLS` et le system prompt suffisent.

```python
# Avant (problématique)
payload = f"{user_text}\n\n{self.skill_context}{project_context}" if not messages else ...

# Après (correct)
payload = f"[projet: \"{project_name}\"] {user_text}{project_context}"
```

### Problème 2 — La voix s'affichait puis disparaissait

**Cause** : le handler `voice-selected` appelait `saveSelection.mutate()` (POST), dont le `onSuccess` déclenchait `selectionQuery.refetch()` (GET). Si le GET renvoyait un profil sans `tts_voice_id` (parce qu'on n'écrivait pas dans le bon store), le `useEffect` réinitialisait `selectedVoiceId` à `null`.

**Solution** : écriture dans les deux stores + mise à jour immédiate sans attendre la mutation.

### Problème 3 — Délai visuel

**Cause** : la séquence `mutate → onSuccess → refetch` ajoutait ~600ms avant la mise à jour visuelle.

**Solution** : `setSelectedVoiceId` en premier (synchrone, 0ms), puis `invalidateQueries` en arrière-plan.

---

## Pattern réutilisable

Ce schéma peut s'appliquer à n'importe quel outil du chat agent :

1. **Déclarer un tool** dans `TOOLS[]` avec une description claire
2. **Implémenter** son exécution dans `execute_tool()` 
3. **Émettre** un `CustomEvent` dans `ChatPanel.tsx` sur réception du `tool_result`
4. **Écouter** l'événement dans le composant React concerné et mettre à jour l'état local immédiatement

```
Claude tool_call  →  execute_tool  →  WS tool_result  →  CustomEvent  →  setState
```
