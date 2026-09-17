export interface Settings {
  plex_url: string;
  plex_token_set: boolean;
  mediux_token_set: boolean;
  kometa_asset_dir: string;
}

export interface Library {
  id: number;
  plex_key: string;
  title: string;
  media_type: "movie" | "show";
  selected: boolean;
}

export interface MediaItem {
  id: number;
  library_id: number;
  library_title: string;
  rating_key: string;
  media_type: "movie" | "show";
  title: string;
  year: number | null;
  tmdb_id: string | null;
  tvdb_id: string | null;
  imdb_id: string | null;
  media_path: string | null;
  asset_name: string;
  last_exported_set_id: string | null;
}

export type AssetType = "poster" | "background" | "season_poster" | "titlecard";

export interface MediuxAsset {
  id: string;
  asset_type: AssetType;
  modified_on: string;
  filesize: string | null;
  src: string | null;
  blurhash: string | null;
  language: string | null;
  season_number: number | null;
  episode_number: number | null;
  title: string | null;
  preview_url: string;
}

export interface MediuxSet {
  id: string;
  title: string;
  creator: string;
  date_updated: string;
  popularity: number;
  popularity_global: number;
  assets: MediuxAsset[];
}

export interface ExportPlan {
  media_item_id: number;
  set_id: string;
  entries: Array<{
    asset_id: string;
    asset_type: AssetType;
    target_path: string;
    exists: boolean;
    action: "create" | "replace";
  }>;
  requires_confirmation: boolean;
}

export interface ExportResult {
  job_id: number;
  status: "completed" | "partial" | "failed";
  entries: Array<{
    asset_id: string;
    target_path: string;
    status: "created" | "replaced" | "unchanged" | "failed";
    message: string | null;
  }>;
}
