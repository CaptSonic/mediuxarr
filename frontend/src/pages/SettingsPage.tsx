import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Server, ShieldCheck } from "lucide-react";
import { api } from "../api";

export function SettingsPage() {
  const client = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const [form, setForm] = useState({ plex_url: "", plex_token: "", mediux_token: "", kometa_asset_dir: "" });
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (settings.data) {
      setForm((current) => ({
        ...current,
        plex_url: settings.data.plex_url,
        kometa_asset_dir: settings.data.kometa_asset_dir,
      }));
    }
  }, [settings.data]);

  const save = useMutation({
    mutationFn: () => api.saveSettings({
      plex_url: form.plex_url,
      plex_token: form.plex_token || undefined,
      mediux_token: form.mediux_token || undefined,
      kometa_asset_dir: form.kometa_asset_dir,
    }),
    onSuccess: (data) => {
      client.setQueryData(["settings"], data);
      setForm((current) => ({ ...current, plex_token: "", mediux_token: "" }));
      setNotice("Einstellungen gespeichert.");
    },
  });

  const testPlex = useMutation({ mutationFn: api.testPlex, onSuccess: (data) => setNotice(data.message) });
  const testMediux = useMutation({ mutationFn: api.testMediux, onSuccess: (data) => setNotice(data.message) });
  const error = save.error ?? testPlex.error ?? testMediux.error;

  return (
    <section>
      <header className="page-header">
        <div><span className="eyebrow">Konfiguration</span><h1>Einstellungen</h1><p>Plex liest die Bibliothek; MediUX liefert Bilder; Kometa übernimmt Upload und Overlays.</p></div>
      </header>
      <div className="settings-grid">
        <article className="panel">
          <div className="panel-title"><Server /><div><h2>Plex</h2><p>Lokale Server-URL und Zugriffstoken</p></div></div>
          <label>Server-URL<input value={form.plex_url} onChange={(e) => setForm({ ...form, plex_url: e.target.value })} placeholder="http://plex:32400" /></label>
          <label>Token<input type="password" value={form.plex_token} onChange={(e) => setForm({ ...form, plex_token: e.target.value })} placeholder={settings.data?.plex_token_set ? "Token ist gespeichert" : "X-Plex-Token"} /></label>
          <button className="button secondary" onClick={() => testPlex.mutate()} disabled={testPlex.isPending}>Plex-Verbindung testen</button>
        </article>
        <article className="panel">
          <div className="panel-title"><KeyRound /><div><h2>MediUX</h2><p>API-Token bleibt ausschließlich im Backend</p></div></div>
          <label>API-Token<input type="password" value={form.mediux_token} onChange={(e) => setForm({ ...form, mediux_token: e.target.value })} placeholder={settings.data?.mediux_token_set ? "Token ist gespeichert" : "MediUX API-Token"} /></label>
          <button className="button secondary" onClick={() => testMediux.mutate()} disabled={testMediux.isPending}>MediUX-Verbindung testen</button>
        </article>
        <article className="panel wide">
          <div className="panel-title"><ShieldCheck /><div><h2>Kometa-Assets</h2><p>Zielverzeichnis mit <code>asset_folders: true</code></p></div></div>
          <label>Asset-Verzeichnis<input value={form.kometa_asset_dir} onChange={(e) => setForm({ ...form, kometa_asset_dir: e.target.value })} placeholder="/kometa-assets" /></label>
          <div className="callout">Der Pfad muss für den mediuxarr-Container beschreibbar sein und auf dasselbe Host-Verzeichnis zeigen, das Kometa als Asset-Verzeichnis verwendet.</div>
        </article>
      </div>
      {notice && <div className="notice success"><CheckCircle2 size={18} />{notice}</div>}
      {error && <div className="notice error">{error.message}</div>}
      <div className="page-actions"><button className="button primary" onClick={() => save.mutate()} disabled={save.isPending || !form.kometa_asset_dir}>Einstellungen speichern</button></div>
    </section>
  );
}
