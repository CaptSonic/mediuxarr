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

1. `.env.example` nach `.env` kopieren.
2. Mindestens diese Werte ergänzen:

```env
MEDIUXARR_SECRET_KEY=eine-lange-zufaellige-zeichenfolge
MEDIUXARR_MEDIUX_API_TOKEN=your-mediux-api-token
KOMETA_ASSET_PATH=/mnt/appdata/kometa/assets
TZ=Europe/Berlin
```

Der MediUX-Token kann damit vollständig über die `.env` bereitgestellt werden. Ein später über
die Weboberfläche gespeicherter Token hat Vorrang vor `MEDIUXARR_MEDIUX_API_TOKEN`.

3. Da Repository und GHCR-Paket privat sind, einmalig bei GHCR anmelden. Dafür wird ein
   GitHub Personal Access Token mit mindestens `read:packages` benötigt:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u CaptSonic --password-stdin
```

4. Container starten:

```bash
docker compose pull
docker compose up -d
```

Standardmäßig wird `ghcr.io/captsonic/mediuxarr:latest` verwendet. Eine feste Version kann in
der `.env` gewählt werden:

```env
MEDIUXARR_VERSION=0.1.0
```

5. Weboberfläche unter `http://localhost:8000` öffnen.

Der Hostpfad `KOMETA_ASSET_PATH` muss derselbe Ordner sein, den Kometa als `asset_directory` verwendet. Im mediuxarr-Container erscheint er als `/kometa-assets`.

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
