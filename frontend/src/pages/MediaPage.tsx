import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Download, Film, FolderOpen, RefreshCw, Search, Tv, X } from "lucide-react";
import { api } from "../api";
import type { ExportPlan, MediaItem, MediuxAsset, MediuxSet } from "../types";

const labels = { poster: "Poster", background: "Backdrop", season_poster: "Staffelposter", titlecard: "Titelkarte" };

export function MediaPage() {
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [active, setActive] = useState<MediaItem | null>(null);
  const [activeSet, setActiveSet] = useState<MediuxSet | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [plan, setPlan] = useState<ExportPlan | null>(null);
  const [confirmOverwrite, setConfirmOverwrite] = useState(false);
  const [result, setResult] = useState("");
  const media = useQuery({ queryKey: ["media", search], queryFn: () => api.getMedia(search) });
  const sets = useQuery({ queryKey: ["sets", active?.id], queryFn: () => api.getSets(active!.id), enabled: Boolean(active?.tmdb_id) });
  const chosenAssets = useMemo(() => activeSet?.assets.filter((asset) => selected.includes(asset.id)) ?? [], [activeSet, selected]);
  const movies = useMemo(() => media.data?.filter((item) => item.media_type === "movie") ?? [], [media.data]);
  const shows = useMemo(() => media.data?.filter((item) => item.media_type === "show") ?? [], [media.data]);

  const planMutation = useMutation({ mutationFn: () => api.planExport(active!.id, activeSet!.id, chosenAssets), onSuccess: (data) => { setPlan(data); setConfirmOverwrite(false); } });
  const exportMutation = useMutation({
    mutationFn: () => api.executeExport(active!.id, activeSet!.id, chosenAssets, confirmOverwrite),
    onSuccess: async (data) => { setResult(`Export ${data.status}: ${data.entries.filter((entry) => entry.status !== "failed").length} Assets verarbeitet.`); setPlan(null); await client.invalidateQueries({ queryKey: ["media"] }); },
  });
  const refreshMutation = useMutation({
    mutationFn: api.refreshMediaAvailability,
    onSuccess: async () => client.invalidateQueries({ queryKey: ["media"] }),
  });

  const open = (item: MediaItem) => { setActive(item); setActiveSet(null); setSelected([]); setPlan(null); setResult(""); };
  const chooseSet = (set: MediuxSet) => { setActiveSet(set); setSelected(set.assets.map((asset) => asset.id)); setPlan(null); };
  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  const close = () => { setActive(null); setActiveSet(null); setPlan(null); };

  return (
    <section>
      <header className="page-header split">
        <div><span className="eyebrow">Kometa-Asset-Browser</span><h1>Medien</h1><p>Es werden nur Plex-Medien angezeigt, für die MediUX Dateien anbietet.</p></div>
        <div className="media-tools">
          <div className="search"><Search size={18} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Titel oder Asset-Ordner suchen" /></div>
          <button className="button secondary" onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending}><RefreshCw size={17} /> MediUX aktualisieren</button>
        </div>
      </header>
      {(media.error || refreshMutation.error) && <div className="notice error">{(media.error ?? refreshMutation.error)?.message}</div>}
      {media.isLoading ? <div className="loading">MediUX-Verfügbarkeit wird geprüft…</div> : <>
        <MediaSection title="Filme" icon={<Film />} items={movies} onOpen={open} />
        <MediaSection title="Serien" icon={<Tv />} items={shows} onOpen={open} />
      </>}

      {active && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}>
        <div className="modal">
          <div className="modal-header"><div><span className="eyebrow">{active.media_type === "movie" ? "Film" : "Serie"}</span><h2>{active.title} {active.year ? `(${active.year})` : ""}</h2><p>Kometa-Ordner: <code>{active.asset_name}</code></p></div><button className="icon-button" onClick={close}><X /></button></div>
          {!active.tmdb_id ? <div className="notice error">Dieses Medium hat in Plex keine TMDb-ID und kann nicht sicher zugeordnet werden.</div> : sets.isLoading ? <div className="loading">MediUX-Sets werden geladen…</div> :
            <div className="set-layout">
              <aside className="set-list">
                {sets.data?.map((set) => <button key={set.id} className={activeSet?.id === set.id ? "active" : ""} onClick={() => chooseSet(set)}><strong>{set.title}</strong><span>von {set.creator}</span><small>{set.assets.length} Assets</small></button>)}
                {sets.data?.length === 0 && <p>Keine MediUX-Sets gefunden.</p>}
              </aside>
              <div className="asset-area">
                {activeSet ? <>
                  <div className="asset-toolbar"><div><h3>{activeSet.title}</h3><p>Wähle die Bilder, die in den Kometa-Ordner geschrieben werden.</p></div><span>{selected.length}/{activeSet.assets.length} ausgewählt</span></div>
                  <div className="asset-grid">{activeSet.assets.map((asset) => <AssetCard key={asset.id} asset={asset} selected={selected.includes(asset.id)} onToggle={() => toggle(asset.id)} />)}</div>
                  {(planMutation.error || exportMutation.error) && <div className="notice error">{(planMutation.error ?? exportMutation.error)?.message}</div>}
                  {result && <div className="notice success"><Check size={18} />{result} Starte Kometa, um Assets und Overlays anzuwenden.</div>}
                  <div className="modal-actions"><button className="button primary" disabled={!selected.length || planMutation.isPending} onClick={() => planMutation.mutate()}><Download size={17} /> Export prüfen</button></div>
                </> : <div className="empty compact"><FolderOpen /><h2>Set auswählen</h2><p>Wähle links ein MediUX-Set für die Vorschau.</p></div>}
              </div>
            </div>}
        </div>
      </div>}
      {plan && <div className="modal-backdrop confirm-layer"><div className="confirm-dialog"><h2>Export bestätigen</h2><p>Diese Dateien werden in den Kometa-Asset-Ordner geschrieben:</p><div className="plan-list">{plan.entries.map((entry) => <div key={entry.asset_id} className={entry.exists ? "conflict" : ""}><span>{entry.exists ? <AlertTriangle /> : <Check />}</span><code>{entry.target_path}</code><strong>{entry.exists ? "Ersetzen" : "Neu"}</strong></div>)}</div>{plan.requires_confirmation && <label className="confirm-check"><input type="checkbox" checked={confirmOverwrite} onChange={(e) => setConfirmOverwrite(e.target.checked)} /><span>Ich bestätige, dass vorhandene Assets ohne Backup ersetzt werden.</span></label>}<div className="modal-actions"><button className="button secondary" onClick={() => setPlan(null)}>Abbrechen</button><button className="button danger" disabled={plan.requires_confirmation && !confirmOverwrite || exportMutation.isPending} onClick={() => exportMutation.mutate()}>Assets exportieren</button></div></div></div>}
    </section>
  );
}

function MediaSection({ title, icon, items, onOpen }: { title: string; icon: React.ReactNode; items: MediaItem[]; onOpen: (item: MediaItem) => void }) {
  return <section className="media-section">
    <div className="section-heading"><div>{icon}<h2>{title}</h2></div><span>{items.length}</span></div>
    {items.length ? <div className="media-grid">
      {items.map((item) => <button className="media-card" key={item.id} onClick={() => onOpen(item)}>
        <div className="media-placeholder">{item.media_type === "movie" ? <Film /> : <Tv />}</div>
        <div className="media-copy"><strong>{item.title}</strong><span>{item.year ?? "–"} · {item.library_title}</span><small><FolderOpen size={13} /> {item.asset_name}</small></div>
        <span className="status-dot matched" title={item.mediux_checked_at ? `MediUX geprüft: ${new Date(item.mediux_checked_at).toLocaleString("de-DE")}` : "Bei MediUX verfügbar"} />
      </button>)}
    </div> : <div className="empty compact">{icon}<h2>Keine {title.toLowerCase()} mit MediUX-Dateien</h2><p>Starte einen Plex-Scan oder aktualisiere den MediUX-Cache.</p></div>}
  </section>;
}

function AssetCard({ asset, selected, onToggle }: { asset: MediuxAsset; selected: boolean; onToggle: () => void }) {
  const position = asset.asset_type === "season_poster" ? `Staffel ${asset.season_number}` : asset.asset_type === "titlecard" ? `S${String(asset.season_number).padStart(2, "0")}E${String(asset.episode_number).padStart(2, "0")}` : "";
  return <button className={`asset-card ${selected ? "selected" : ""} ${asset.asset_type === "background" || asset.asset_type === "titlecard" ? "wide-image" : ""}`} onClick={onToggle}>
    <div className="asset-image"><img src={asset.preview_url} alt={asset.title ?? labels[asset.asset_type]} loading="lazy" /><span className="checkmark">{selected && <Check size={15} />}</span></div>
    <div><strong>{labels[asset.asset_type]}</strong><span>{position}{asset.language ? `${position ? " · " : ""}${asset.language}` : ""}</span>{asset.title && <small>{asset.title}</small>}</div>
  </button>;
}
