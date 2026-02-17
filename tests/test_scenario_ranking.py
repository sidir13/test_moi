import json

from memoiredesterritoires.scenario_ranking.rank_scenarios import rank_scenarios_against_config


def test_rank_scenarios_reranks_by_titles(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"scenario_config": {}}), encoding="utf-8")

    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()

    titles = [
        "Mémoires d'une ouvrière des chantiers navals",
        "Lettre à ma fille : Mémoires d'une soudeuse des chantiers navals",
        "Mains de fer, cœur d'acier : chronique des ouvriers des chantiers navals",
        "Mémoires d'un savoir-faire : l'apprentissage et l'évolution d'un métier",
    ]
    for idx, title in enumerate(titles, start=1):
        payload = {
            "scenario_id": idx,
            "titre": title,
            "parties": [
                {"partie_id": 1, "titre": "Partie", "texte_narration": f"Texte {idx}"}
            ],
        }
        with open(scenarios_dir / f"scenario_{idx}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def fake_llm(_prompt: str) -> str:
        return (
            "Scénarios disponibles\n\n"
            "Scénario 4 — Mémoires d'un savoir-faire : l'apprentissage et l'évolution d'un métier\n"
            "Scénario 2 — Lettre à ma fille : Mémoires d'une soudeuse des chantiers navals\n"
            "Scénario 3 — Mains de fer, cœur d'acier : chronique des ouvriers des chantiers navals\n"
            "Scénario 1 — Mémoires d'une ouvrière des chantiers navals\n"
        )

    monkeypatch.setattr(
        "memoiredesterritoires.scenario_ranking.rank_scenarios._call_llm",
        fake_llm,
    )

    result = rank_scenarios_against_config(
        config_path=str(config_path),
        scenarios_dir=str(scenarios_dir),
        project_name="test",
    )

    assert result["ranking"] == [
        "scenario_4.json",
        "scenario_2.json",
        "scenario_3.json",
        "scenario_1.json",
    ]

    with open(config_path, "r", encoding="utf-8") as handle:
        updated = json.load(handle)
    assert updated["scenario_config"]["scenario_ranking"] == result["ranking"]
