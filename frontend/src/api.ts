import type {
  ExportPlan,
  ExportResult,
  Library,
  MediaItem,
  MediuxAsset,
  MediuxSet,
  Settings,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? "Unbekannter Fehler");
  }
  return response.json() as Promise<T>;
}

export const api = {
  getSettings: () => request<Settings>("/api/settings"),
  saveSettings: (payload: {
    plex_url: string;
    plex_token?: string;
    mediux_token?: string;
    kometa_asset_dir: string;
  }) => request<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),
  testPlex: () => request<{ message: string }>("/api/settings/test-plex", { method: "POST" }),
  testMediux: () => request<{ message: string }>("/api/settings/test-mediux", { method: "POST" }),
  getLibraries: () => request<Library[]>("/api/libraries"),
  syncLibraries: () => request<Library[]>("/api/libraries/sync", { method: "POST" }),
  selectLibraries: (library_ids: number[]) =>
    request<Library[]>("/api/libraries/selection", {
      method: "PUT",
      body: JSON.stringify({ library_ids }),
    }),
  scan: () => request<{ items: number; mediux_checked: number }>("/api/scan", { method: "POST" }),
  getMedia: (search = "") =>
    request<MediaItem[]>(`/api/media?search=${encodeURIComponent(search)}`),
  refreshMediaAvailability: () =>
    request<{ checked: number; available: number }>("/api/media/availability/refresh", {
      method: "POST",
    }),
  getSets: (mediaId: number) => request<MediuxSet[]>(`/api/media/${mediaId}/sets`),
  planExport: (mediaId: number, setId: string, assets: MediuxAsset[]) =>
    request<ExportPlan>(`/api/media/${mediaId}/export/plan`, {
      method: "POST",
      body: JSON.stringify({ set_id: setId, assets: assets.map(exportAsset) }),
    }),
  executeExport: (
    mediaId: number,
    setId: string,
    assets: MediuxAsset[],
    confirm_overwrite: boolean,
  ) =>
    request<ExportResult>(`/api/media/${mediaId}/export`, {
      method: "POST",
      body: JSON.stringify({
        set_id: setId,
        assets: assets.map(exportAsset),
        confirm_overwrite,
      }),
    }),
};

function exportAsset(asset: MediuxAsset) {
  return {
    asset_id: asset.id,
    asset_type: asset.asset_type,
    modified_on: asset.modified_on,
    season_number: asset.season_number,
    episode_number: asset.episode_number,
  };
}
