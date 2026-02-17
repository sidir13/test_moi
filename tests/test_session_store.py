from server.session_store import SessionStore


def _create_store(tmp_path):
    return SessionStore(tmp_path)


def test_set_selected_scenario_preserves_audio_when_data_unchanged(tmp_path):
    store = _create_store(tmp_path)
    session = store.create_session("proj", "project_details")
    session_id = session["session_id"]
    scenario = {"titre": "A", "parties": [{"titre": "Partie", "texte_narration": "Texte"}]}

    store.set_selected_scenario(session_id, scenario)
    meta = {"path": "audio.wav", "language": "fr"}
    store.save_scenario_audio(session_id, meta)

    store.set_selected_scenario(session_id, dict(scenario))
    assert store.get_scenario_audio(session_id) == meta


def test_set_selected_scenario_resets_audio_when_data_changes(tmp_path):
    store = _create_store(tmp_path)
    session_id = store.create_session("proj", "project_details")["session_id"]
    scenario = {"titre": "A", "parties": [{"titre": "Partie", "texte_narration": "Texte"}]}
    store.set_selected_scenario(session_id, scenario)
    store.save_scenario_audio(session_id, {"path": "audio.wav"})

    updated = {"titre": "B", "parties": scenario["parties"]}
    store.set_selected_scenario(session_id, updated)

    assert store.get_scenario_audio(session_id) is None
