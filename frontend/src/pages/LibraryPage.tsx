import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Film, RefreshCw, ScanSearch, Tv } from "lucide-react";
import { api } from "../api";

export function LibraryPage() {
  const client = useQueryClient();
  const libraries = useQuery({ queryKey: ["libraries"], queryFn: api.getLibraries });
  const [selected, setSelected] = useState<number[]>([]);
  const [notice, setNotice] = useState("");
  useEffect(() => { if (libraries.data) setSelected(libraries.data.filter((entry) => entry.selected).map((entry) => entry.id)); }, [libraries.data]);

  const sync = useMutation({
    mutationFn: api.syncLibraries,
    onSuccess: (data) => { client.setQueryData(["libraries"], data); setNotice(`${data.length} Bibliotheken geladen.`); },
  });
  const save = useMutation({
    mutationFn: () => api.selectLibraries(selected),
    onSuccess: (data) => { client.setQueryData(["libraries"], data); setNotice("Bibliotheksauswahl gespeichert."); },
  });
  const scan = useMutation({
    mutationFn: api.scan,
    onSuccess: async (data) => { await client.invalidateQueries({ queryKey: ["media"] }); setNotice(`${data.items} Medien wurden eingelesen.`); },
  });
  const error = sync.error ?? save.error ?? scan.error;

  const toggle = (id: number) => setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  return (
    <section>
      <header className="page-header split">
        <div><span className="eyebrow">Plex-Quelle</span><h1>Bibliotheken</h1><p>Wähle Film- und Serienbibliotheken, deren Medien in MediUX gesucht werden.</p></div>
        <button className="button secondary" onClick={() => sync.mutate()} disabled={sync.isPending}><RefreshCw size={17} /> Bibliotheken laden</button>
      </header>
      <div className="library-list">
        {libraries.data?.map((library) => (
          <label className={`library-card ${selected.includes(library.id) ? "selected" : ""}`} key={library.id}>
            <input type="checkbox" checked={selected.includes(library.id)} onChange={() => toggle(library.id)} />
            <div className="library-icon">{library.media_type === "movie" ? <Film /> : <Tv />}</div>
            <div><strong>{library.title}</strong><span>{library.media_type === "movie" ? "Filme" : "Serien"}</span></div>
          </label>
        ))}
        {!libraries.isLoading && libraries.data?.length === 0 && <div className="empty"><Database /><h2>Noch keine Bibliotheken</h2><p>Speichere zuerst die Plex-Verbindung und lade dann die Bibliotheken.</p></div>}
      </div>
      {notice && <div className="notice success">{notice}</div>}
      {error && <div className="notice error">{error.message}</div>}
      <div className="page-actions">
        <button className="button secondary" onClick={() => save.mutate()} disabled={save.isPending}>Auswahl speichern</button>
        <button className="button primary" onClick={() => scan.mutate()} disabled={scan.isPending || selected.length === 0}><ScanSearch size={17} /> Jetzt scannen</button>
      </div>
    </section>
  );
}
