import { DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import {
  API_BASE_URL,
  advanceStep,
  fetchSelectedScenario,
  selectScenario,
  fetchScenarioAudio,
  synthesizeScenarioAudio,
  getScenarioAudioUrl,
  fetchScenarioImages,
  uploadScenarioImage,
  deleteScenarioImage,
  reorderScenarioImages,
  fetchSlideshow,
  createSlideshow,
  getScenarioSlideshowUrl
} from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

type ScenarioPartDraft = { titre: string; texte_narration: string };

export function ScenarioEditView() {
  const { sessionId, setCurrentStep, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [partsDraft, setPartsDraft] = useState<ScenarioPartDraft[]>([]);
  const [freeText, setFreeText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [audioStatus, setAudioStatus] = useState<string | null>(null);
  const [imageStatus, setImageStatus] = useState<string | null>(null);
  const [videoStatus, setVideoStatus] = useState<string | null>(null);
  const [isDraggingFiles, setIsDraggingFiles] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const selectionQuery = useQuery({
    queryKey: ["selected-scenario", sessionId],
    queryFn: () => fetchSelectedScenario(sessionId!),
    enabled: Boolean(sessionId)
  });

  const audioQuery = useQuery({
    queryKey: ["scenario-audio", sessionId],
    queryFn: () => fetchScenarioAudio(sessionId!),
    enabled: Boolean(sessionId)
  });
  const refetchAudio = audioQuery.refetch;

  const imagesQuery = useQuery({
    queryKey: ["scenario-images", sessionId],
    queryFn: () => fetchScenarioImages(sessionId!),
    enabled: Boolean(sessionId)
  });

  const slideshowQuery = useQuery({
    queryKey: ["scenario-slideshow", sessionId],
    queryFn: () => fetchSlideshow(sessionId!),
    enabled: Boolean(sessionId)
  });

  useEffect(() => {
    if (!selectionQuery.data) return;
    const payload = extractScenario(selectionQuery.data);
    setTitle(payload.titre ?? "");
    if (Array.isArray(payload.parties) && payload.parties.length > 0) {
      setPartsDraft(
        payload.parties.map((part: any, idx: number) => ({
          titre: part?.titre ?? `Partie ${idx + 1}`,
          texte_narration: part?.texte_narration ?? part?.texte ?? ""
        }))
      );
      setFreeText("");
    } else {
      setPartsDraft([]);
      setFreeText(payload.texte_narration ?? payload.texte ?? "");
    }
  }, [selectionQuery.data]);

  const audioJobStatus = audioQuery.data?.status;
  const isAudioProcessing = audioJobStatus === "pending" || audioJobStatus === "running";
  const hasAudioError = audioJobStatus === "failed";
  const audioReady = audioJobStatus === "done" && Boolean(audioQuery.data?.path);

  useEffect(() => {
    if (!sessionId) return;
    if (isAudioProcessing) {
      const interval = setInterval(() => {
        refetchAudio();
      }, 4000);
      return () => clearInterval(interval);
    }
  }, [sessionId, isAudioProcessing, refetchAudio]);

  useEffect(() => {
    if (isAudioProcessing) {
      setAudioStatus("Audio en cours de génération…");
    } else if (hasAudioError) {
      setAudioStatus(
        audioQuery.data?.error
          ? `Échec de la génération : ${audioQuery.data.error}`
          : "Impossible de générer l'audio."
      );
    } else if (audioJobStatus === "done") {
      setAudioStatus("Audio disponible.");
    }
  }, [audioJobStatus, isAudioProcessing, hasAudioError, audioQuery.data?.error]);

  const audioSrc = useMemo(() => {
    if (!sessionId || !audioReady || !audioQuery.data?.path) return null;
    const base = getScenarioAudioUrl(sessionId).replace(/\/$/, "");
    const cacheBust = audioQuery.data.generated_at ? `?ts=${encodeURIComponent(audioQuery.data.generated_at)}` : "";
    return `${base}${cacheBust}`;
  }, [audioQuery.data, sessionId, audioReady]);

  const slideshowSrc = useMemo(() => {
    if (!sessionId || !slideshowQuery.data?.path) return null;
    const base = getScenarioSlideshowUrl(sessionId).replace(/\/$/, "");
    const cacheBust = slideshowQuery.data.created_at ? `?ts=${encodeURIComponent(slideshowQuery.data.created_at)}` : "";
    return `${base}${cacheBust}`;
  }, [sessionId, slideshowQuery.data]);

  const images = imagesQuery.data ?? [];
  const imagesLimitReached = images.length >= 10;
  const apiBase = useMemo(() => (API_BASE_URL || "").replace(/\/$/, ""), []);

  if (!sessionId) return <p>Démarrez une session.</p>;
  if (selectionQuery.isLoading) return <p>Chargement du scénario sélectionné...</p>;
  if (!selectionQuery.data) return <p>Aucun scénario sélectionné. Retournez à l'étape précédente.</p>;

  const persistScenario = async () => {
    if (!sessionId || !selectionQuery.data) return;
    const updated = buildUpdatedScenario(selectionQuery.data, title, partsDraft, freeText);
    await selectScenario(sessionId, updated);
    await queryClient.invalidateQueries({ queryKey: ["selected-scenario", sessionId] });
  };

  const handleUploadImages = async (files: FileList | null) => {
    if (!sessionId || !files) return;
    try {
      setImageStatus("Téléversement des images en cours...");
      for (const file of Array.from(files)) {
        if ((imagesQuery.data?.length ?? 0) >= 10) break;
        await uploadScenarioImage(sessionId, file);
      }
      await imagesQuery.refetch();
      setImageStatus("Images ajoutées.");
    } catch (err) {
      console.error("Image upload failed", err);
      setImageStatus("Impossible d'ajouter les images.");
    }
  };

  const openFilePicker = () => {
    if (imagesLimitReached) return;
    fileInputRef.current?.click();
  };

  const handleDropFiles = async (evt: DragEvent<HTMLDivElement>) => {
    evt.preventDefault();
    setIsDraggingFiles(false);
    if (imagesLimitReached) return;
    if (evt.dataTransfer.files && evt.dataTransfer.files.length > 0) {
      await handleUploadImages(evt.dataTransfer.files);
      evt.dataTransfer.clearData();
    }
  };

  const handleDeleteImage = async (imageId: string) => {
    if (!sessionId) return;
    await deleteScenarioImage(sessionId, imageId);
    await imagesQuery.refetch();
  };

  const handleReorder = async (fromId: string, toId: string) => {
    if (!sessionId || !imagesQuery.data) return;
    const list = [...imagesQuery.data];
    const fromIndex = list.findIndex((img) => img.id === fromId);
    const toIndex = list.findIndex((img) => img.id === toId);
    if (fromIndex === -1 || toIndex === -1) return;
    const reordered = [...list];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved);
    await reorderScenarioImages(
      sessionId,
      reordered.map((img) => img.id)
    );
    await imagesQuery.refetch();
  };

  const handleDragStart = (evt: DragEvent<HTMLDivElement>, id: string) => {
    evt.dataTransfer.setData("text/plain", id);
  };

  const handleDropOnImage = async (evt: DragEvent<HTMLDivElement>, targetId: string) => {
    evt.preventDefault();
    const fromId = evt.dataTransfer.getData("text/plain");
    if (fromId && fromId !== targetId) {
      await handleReorder(fromId, targetId);
    }
  };

  const ensureSlideshowIfNeeded = async (force = false) => {
    if (!sessionId) return;
    if ((imagesQuery.data?.length ?? 0) === 0) return;
    if (!audioQuery.data?.path) {
      setVideoStatus("Générez l'audio avant de créer un diaporama.");
      return;
    }
    if (!force && slideshowQuery.data?.path) {
      return;
    }
    try {
      setVideoStatus("Création du diaporama...");
      await createSlideshow(sessionId);
      await slideshowQuery.refetch();
      setVideoStatus("Diaporama mis à jour.");
    } catch (err) {
      console.error("Slideshow generation failed", err);
      const apiMessage =
        axios.isAxiosError(err) && err.response?.data?.detail
          ? err.response.data.detail
          : "Impossible de créer le diaporama.";
      setVideoStatus(apiMessage);
    }
  };

  const handleCreateSlideshow = async () => {
    if ((imagesQuery.data?.length ?? 0) === 0) {
      setVideoStatus("Ajoutez des images avant de créer un diaporama.");
      return;
    }
    if (!audioQuery.data?.path) {
      setVideoStatus("Générez l'audio avant de créer un diaporama.");
      return;
    }
    await ensureSlideshowIfNeeded(true);
  };

  const handleSubmit = async (evt: FormEvent) => {
    evt.preventDefault();
    setStatus("Sauvegarde de vos modifications...");
    await persistScenario();
    const refreshed = await audioQuery.refetch();
    if (!refreshed.data?.path) {
      setStatus("Générez l'audio avant de continuer vers la validation finale.");
      return;
    }
    await ensureSlideshowIfNeeded();
    await advanceStep(sessionId, "scenario_edit", { titre: title });
    updateProgress({ scenarioEdited: true });
    setCurrentStep("final_validation");
    navigate("/step/final_validation");
    setStatus(null);
  };

  const saveDraft = async () => {
    setStatus("Scénario en cours d'enregistrement...");
    await persistScenario();
    setStatus("Scénario mis à jour.");
  };

  const regenerateAudio = async () => {
    if (!sessionId) return;
    setAudioStatus("Génération d'un nouvel audio...");
    await persistScenario();
    try {
      const job = await synthesizeScenarioAudio(sessionId);
      if (job?.status && job.status !== "done") {
        setAudioStatus("Audio en cours de génération…");
      } else {
        setAudioStatus("Audio régénéré.");
      }
      await audioQuery.refetch();
    } catch (err) {
      console.error("Audio regeneration failed", err);
      setAudioStatus(extractErrorMessage(err) ?? "Impossible de régénérer l'audio.");
    }
  };

  const addPart = () => {
    setPartsDraft((prev) => [...prev, { titre: `Partie ${prev.length + 1}`, texte_narration: "" }]);
    setFreeText("");
  };

  const removePart = (index: number) => {
    setPartsDraft((prev) => prev.filter((_, idx) => idx !== index));
  };

  const scenarioTitle = title?.trim();
  const heading = scenarioTitle && scenarioTitle.length > 0 ? `Modifier le scénario — ${scenarioTitle}` : "Modifier le scénario";

  return (
    <div className="step-view">
      <h2>{heading}</h2>
      <form onSubmit={handleSubmit} className="form-grid">

        <section className="card">
          <h3>Structure narrative</h3>
          {partsDraft.length === 0 ? (
            <>
              <label>
                Corps du scénario
                <textarea rows={10} value={freeText} onChange={(e) => setFreeText(e.target.value)} />
              </label>
              <button type="button" className="link" onClick={addPart}>
                Découper en parties
              </button>
            </>
          ) : (
            <>
              {partsDraft.map((part, idx) => (
                <div className="card" key={idx}>
                  <div
                    style={{
                      border: "1px solid var(--border, #d0d7de)",
                      borderRadius: 6,
                      padding: "0.4rem 0.6rem",
                      background: "var(--card-bg, #f5f6f8)",
                      marginBottom: "0.5rem",
                      fontWeight: 600
                    }}
                    aria-label={`Titre de la partie ${idx + 1}`}
                  >
                    {part.titre || `Partie ${idx + 1}`}
                  </div>
                  <label>
                    Contenu
                    <textarea
                      rows={6}
                      value={part.texte_narration}
                      onChange={(e) =>
                        setPartsDraft((prev) =>
                          prev.map((p, i) => (i === idx ? { ...p, texte_narration: e.target.value } : p))
                        )
                      }
                    />
                  </label>
                  <button type="button" className="link" onClick={() => removePart(idx)}>
                    Supprimer cette partie
                  </button>
                </div>
              ))}
              <button type="button" className="link" onClick={addPart}>
                Ajouter une partie
              </button>
            </>
          )}
        </section>

        <section className="card">
          <h3>Pré-écoute audio</h3>
          {audioQuery.isFetching && <p>Chargement de l'audio...</p>}
          {audioSrc && (
            <>
              <audio controls src={audioSrc} preload="auto" />
              {audioQuery.data?.generated_at && (
                <p>Dernière génération : {new Date(audioQuery.data.generated_at).toLocaleString()}</p>
              )}
            </>
          )}
          {!audioSrc && !audioQuery.isFetching && (
            <p>{isAudioProcessing ? "Audio en cours de génération…" : "Aucun audio disponible pour l'instant."}</p>
          )}
          {hasAudioError && (
            <p className="alert error">
              {audioQuery.data?.error ?? "Impossible de générer l'audio. Vérifiez vos paramètres vocaux."}
            </p>
          )}
          <button type="button" onClick={regenerateAudio} disabled={isAudioProcessing}>
            Régénérer l'audio
          </button>
          <p className="hint">
            Le dernier audio est sauvegardé automatiquement. Régénérez uniquement si vous souhaitez une nouvelle version.
          </p>
          {audioStatus && <p>{audioStatus}</p>}
        </section>

        <section className="card">
          <h3>Images pour le diaporama (optionnel)</h3>
          <p>Ajoutez jusqu'à 10 images, réorganisez-les par glisser-déposer et générez un diaporama synchronisé avec l'audio.</p>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            disabled={imagesLimitReached}
            style={{ display: "none" }}
            onChange={(e) => {
              handleUploadImages(e.target.files);
              e.target.value = "";
            }}
          />
          <div
            role="button"
            tabIndex={0}
            aria-disabled={imagesLimitReached}
            onClick={openFilePicker}
            onKeyDown={(evt) => {
              if (evt.key === "Enter" || evt.key === " ") {
                evt.preventDefault();
                openFilePicker();
              }
            }}
            onDragEnter={(evt) => {
              evt.preventDefault();
              if (!imagesLimitReached) {
                setIsDraggingFiles(true);
              }
            }}
            onDragOver={(evt) => {
              evt.preventDefault();
              if (!imagesLimitReached) {
                setIsDraggingFiles(true);
              }
            }}
            onDragLeave={(evt) => {
              evt.preventDefault();
              setIsDraggingFiles(false);
            }}
            onDrop={handleDropFiles}
            style={{
              border: `2px dashed ${isDraggingFiles ? "var(--accent, #2680eb)" : "var(--border, #d0d7de)"}`,
              borderRadius: 12,
              padding: "1.5rem",
              textAlign: "center",
              background: isDraggingFiles ? "rgba(38, 128, 235, 0.08)" : "var(--card-bg, #f9fafb)",
              cursor: imagesLimitReached ? "not-allowed" : "pointer",
              opacity: imagesLimitReached ? 0.5 : 1,
              transition: "background 0.2s ease, border-color 0.2s ease"
            }}
          >
            <strong style={{ display: "block", marginBottom: "0.35rem" }}>
              {imagesLimitReached ? "Limite atteinte" : "Déposez vos visuels ici"}
            </strong>
            <span style={{ color: "var(--text-muted, #444)" }}>
              {imagesLimitReached
                ? "Vous avez déjà ajouté 10 images."
                : "Cliquez ou glissez-déposez jusqu'à 10 images (JPEG ou PNG)."}
            </span>
          </div>
          {imagesLimitReached && <p>Limite atteinte (10 images).</p>}
          {imageStatus && <p>{imageStatus}</p>}
          <div
            className="image-grid"
            style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginTop: "0.5rem" }}
          >
            {images.map((image) => (
              <div
                key={image.id}
                className="image-thumb"
                style={{
                  width: 128,
                  height: 128,
                  position: "relative",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  overflow: "hidden",
                  background: "#000"
                }}
                draggable
                onDragStart={(evt) => handleDragStart(evt, image.id)}
                onDragOver={(evt) => evt.preventDefault()}
                onDrop={(evt) => handleDropOnImage(evt, image.id)}
              >
                <img
                  src={`${apiBase}${image.download_url}`}
                  alt={image.original_name ?? image.filename}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
                <button
                  type="button"
                  onClick={() => handleDeleteImage(image.id)}
                  style={{
                    position: "absolute",
                    top: 4,
                    right: 4,
                    border: "none",
                    background: "rgba(0,0,0,0.6)",
                    color: "#fff",
                    borderRadius: "50%",
                    width: 24,
                    height: 24,
                    cursor: "pointer"
                  }}
                  aria-label="Supprimer cette image"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button type="button" onClick={handleCreateSlideshow} disabled={images.length === 0}>
              Créer le diaporama
            </button>
            {videoStatus && <p>{videoStatus}</p>}
          </div>
          {slideshowSrc && (
            <div style={{ marginTop: "0.5rem" }}>
              <p>Diaporama généré :</p>
              <video controls src={slideshowSrc} style={{ width: "100%", maxHeight: 360 }} />
            </div>
          )}
        </section>

        <div className="card">
          <button type="button" onClick={saveDraft}>
            Sauvegarder le texte
          </button>
          <button type="submit">Valider l'édition</button>
        </div>
      </form>
      {status && <p>{status}</p>}
    </div>
  );
}

function extractScenario(raw: Record<string, any>): Record<string, any> {
  if (raw?.scenario && typeof raw.scenario === "object") {
    return raw.scenario;
  }
  return raw;
}

function buildUpdatedScenario(
  original: Record<string, any>,
  title: string,
  parts: ScenarioPartDraft[],
  freeText: string
) {
  const base = { ...original };
  const target = base.scenario && typeof base.scenario === "object" ? { ...base.scenario } : { ...base };
  target.titre = title;
  if (parts.length > 0) {
    target.parties = parts.map((part, idx) => ({
      titre: part.titre || `Partie ${idx + 1}`,
      texte_narration: part.texte_narration ?? ""
    }));
    delete target.texte;
    delete target.texte_narration;
  } else {
    delete target.parties;
    target.texte_narration = freeText;
  }
  if (base.scenario && typeof base.scenario === "object") {
    return { ...base, scenario: target };
  }
  return target;
}
