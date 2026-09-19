# mediuxarr

`mediuxarr` durchsucht ausgewählte Plex-Bibliotheken, zeigt passende Artwork-Sets von MediUX und exportiert ausgewählte Bilder in einen Kometa-Asset-Ordner. Kometa verwendet diese unveränderten Basisbilder beim nächsten Lauf und rendert die konfigurierten Overlays darüber.

## Funktionsumfang

- Plex-Verbindung per Server-URL und Token
- Auswahl und Scan von Film- und Serienbibliotheken
- sichere Zuordnung über TMDb-GUIDs aus Plex
- MediUX-Setgalerie mit Poster, Backdrops, Staffelpostern und Titelkarten
- Kometa-Ausgabe für `asset_folders: true`
- Konfliktvorschau und ausdrückliche Bestätigung vor dem Ersetzen
- atomare Schreibvorgänge ohne Backup
- Tokens bleiben verschlüsselt im Backend und werden nie an den Browser zurückgegeben

## Kometa-Dateien

```text
assets/
├── Dune (2021)/
│   ├── poster.jpg
│   └── background.jpg
└── Breaking Bad (2008)/
    ├── poster.jpg
    ├── background.jpg
    ├── Season00.jpg
    ├── Season01.jpg
    └── S01E01.jpg
```

Der Ordnername wird bevorzugt aus dem tatsächlichen Medienpfad in Plex abgeleitet. Wenn kein Pfad verfügbar ist, verwendet die Anwendung `Titel (Jahr)`.

## Docker

1. Container starten; eine `.env`-Datei und eine Anmeldung bei GHCR sind nicht erforderlich:

```bash
docker compose up -d
```

Beim ersten Start erzeugt mediuxarr automatisch einen persistenten Schlüssel unter
`./config/.secret_key`. Plex- und MediUX-Zugangsdaten werden anschließend über die
Weboberfläche eingetragen. Als lokaler Kometa-Asset-Ordner wird standardmäßig
`./kometa-assets` verwendet.

2. Weboberfläche unter `http://localhost:8000` öffnen und Plex, MediUX sowie den tatsächlichen
   Kometa-Zielpfad konfigurieren.

Eine optionale `.env` kann weiterhin für abweichende Pfade, Zeitzone, Version oder einen extern
verwalteten Schlüssel verwendet werden. Beispiel:

```env
MEDIUXARR_VERSION=0.2.1
KOMETA_ASSET_PATH=/mnt/appdata/kometa/assets
TZ=Europe/Berlin
```

## Medienübersicht und MediUX-Cache

Die Medienübersicht trennt Filme und Serien in eigene Bereiche. Angezeigt werden ausschließlich
Plex-Medien mit TMDb-ID, für die MediUX mindestens ein Set mit Dateien zurückliefert.

Positive und negative MediUX-Ergebnisse werden persistent in der SQLite-Datenbank unter
`./config` gespeichert. Der Cache ist standardmäßig 24 Stunden gültig. Beim Öffnen der Übersicht
werden nur unbekannte, geänderte oder abgelaufene Einträge erneut geprüft. Über
**MediUX aktualisieren** kann eine vollständige Aktualisierung erzwungen werden.

Die Cache-Einstellungen können optional über die Umgebung angepasst werden:

```env
MEDIUXARR_MEDIUX_CACHE_HOURS=24
MEDIUXARR_MEDIUX_REFRESH_CONCURRENCY=5
```

Der Hostpfad `KOMETA_ASSET_PATH` muss derselbe Ordner sein, den Kometa als `asset_directory`
verwendet. Im mediuxarr-Container erscheint er als `/kometa-assets`.

Beispiel für Kometa:

```yaml
settings:
  asset_directory: /config/assets
  asset_folders: true
```

## Lokale Entwicklung

### Backend

```powershell
cd e:\ENTWICKLUNG\mediuxarr\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

### Frontend

```powershell
cd e:\ENTWICKLUNG\mediuxarr\frontend
npm install
npm run dev
```

Vite leitet `/api` während der Entwicklung an `http://localhost:8000` weiter.

## Tests

```powershell
cd e:\ENTWICKLUNG\mediuxarr\backend
python -m pytest
python -m ruff check app tests

cd e:\ENTWICKLUNG\mediuxarr\frontend
npm run build
```

## Sicherheit und Grenzen

- Den MediUX- oder Plex-Token niemals committen oder im Chat teilen.
- Bereits vorhandene Assets werden ausschließlich nach Bestätigung ersetzt und nicht gesichert.
- `mediuxarr` startet Kometa nicht automatisch und lädt keine Bilder direkt zu Plex hoch.
- Ein Medium ohne TMDb-GUID wird absichtlich nicht über Titel/Jahr geraten.
- Die MediUX-API ist derzeit nicht öffentlich dokumentiert. Ihre Verwendung ist deshalb in einem separaten Provider gekapselt.
