import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { createProject, createSession, fetchProjects, ProjectSummary } from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

export function ProjectSelectionView() {
  const { data, refetch, isLoading } = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const { setProjectName, setSessionId, setCurrentStep, setScenarioTarget } = useSessionStore();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [scenarioTargetDraft, setScenarioTargetDraft] = useState(3);
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!name.trim()) throw new Error("Nom requis");
      await createProject({ name: name.trim(), description, scenario_target: scenarioTargetDraft });
      const session = await createSession(name.trim(), "project_selection", scenarioTargetDraft);
      setProjectName(name.trim());
      setSessionId(session.session_id);
      setCurrentStep("project_details");
      setScenarioTarget(scenarioTargetDraft);
      setName("");
      setDescription("");
      refetch();
      navigate("/step/project_details");
    }
  });

  const handleCreate = (evt: FormEvent) => {
    evt.preventDefault();
    setError(null);
    createMutation.mutate(undefined, {
      onError: (err) => setError((err as Error).message)
    });
  };

  const handleSelect = async (project: ProjectSummary) => {
    try {
      const session = await createSession(project.name, "project_selection", project.scenario_target);
      setProjectName(project.name);
      setSessionId(session.session_id);
      setCurrentStep("project_details");
      setScenarioTarget(project.scenario_target);
      navigate("/step/project_details");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="step-view">
      <h2>Créer ou sélectionner un projet</h2>
      <p>Chaque projet conserve ses audios, scénarios et transcriptions.</p>
      {error && <p className="error">{error}</p>}

      <section className="card">
        <h3>Nouveau projet</h3>
        <form onSubmit={handleCreate} className="form-grid">
          <label>
            Nom
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex: port_nantes" />
          </label>
          <label>
            Description
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </label>
          <label>
            Nombre de scénarios à générer (1 à 5)
            <input
              type="range"
              min={1}
              max={5}
              value={scenarioTargetDraft}
              onChange={(e) => setScenarioTargetDraft(Number(e.target.value))}
            />
            <span>{scenarioTargetDraft} scénario(s)</span>
          </label>
        <button type="submit" disabled={createMutation.isPending}>Créer</button>
        </form>
      </section>

      <section className="card">
        <h3>Projets existants</h3>
        {isLoading ? (
          <p>Chargement...</p>
        ) : data && data.length > 0 ? (
          <ul className="project-list">
            {data.map((project) => (
              <li key={project.name}>
                <button onClick={() => handleSelect(project)}>
                  {project.name} <small>({project.scenario_target} scénarios)</small>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p>Aucun projet enregistré pour le moment.</p>
        )}
      </section>
    </div>
  );
}
