"use client";

import { DragEvent, FormEvent, useRef, useState } from "react";

type UploadState = {
  type: "idle" | "success" | "error" | "loading";
  message: string;
};

export function SecaUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [state, setState] = useState<UploadState>({
    type: "idle",
    message: "Die Datei wird lokal gespeichert und anschließend importiert.",
  });
  const inputRef = useRef<HTMLInputElement>(null);

  function chooseFile(nextFile?: File | null) {
    setFile(nextFile ?? null);
    if (nextFile) {
      setState({ type: "idle", message: `${nextFile.name} bereit zum Import.` });
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files.item(0));
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setState({ type: "error", message: "Bitte zuerst eine seca CSV auswählen." });
      return;
    }
    setState({ type: "loading", message: "seca Datei wird importiert..." });
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/api/upload-seca", {
      method: "POST",
      body: formData,
    });
    const result = await response.json();
    if (!response.ok || result.status !== "success") {
      setState({
        type: "error",
        message: result.message ?? "seca Import fehlgeschlagen. Bitte erkannte Spalten prüfen.",
      });
      return;
    }
    setState({
      type: "success",
      message: result.message ?? "Import erfolgreich.",
    });
    setFile(null);
    inputRef.current?.form?.reset();
    window.location.reload();
  }

  return (
    <section className="upload-panel" aria-label="seca Import">
      <div>
        <span>seca Import</span>
        <h2>seca CSV hier ablegen oder Datei auswählen</h2>
        <p>Die Datei wird lokal gespeichert und anschließend importiert.</p>
      </div>
      <form onSubmit={upload}>
        <label
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onDragEnter={() => setDragging(true)}
          onDragLeave={() => setDragging(false)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
        >
          <input
            accept=".csv,.txt,text/csv,text/plain"
            name="file"
            onChange={(event) => chooseFile(event.target.files?.item(0))}
            ref={inputRef}
            type="file"
          />
          <strong>{file ? file.name : "CSV/TXT ablegen"}</strong>
          <small>PDF wird aktuell noch nicht automatisch geparst.</small>
        </label>
        <button disabled={state.type === "loading"} type="submit">
          {state.type === "loading" ? "Import läuft..." : "Import starten"}
        </button>
      </form>
      <p className={`upload-message ${state.type}`}>{state.message}</p>
    </section>
  );
}
