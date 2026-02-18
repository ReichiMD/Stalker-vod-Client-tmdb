# CLAUDE.md – Projektnotizen für KI-Assistenten

## Projektübersicht

Fork von `plugin.video.stalkervod` v1.2.0 (rickeylohia, GPL-3.0).
Erweitert um direkte TMDB-Metadaten-Integration (Poster, Fanart, Plot, Bewertung).

**Addon-ID:** `plugin.video.stalkervod.tmdb`
**Zielplattform:** Kodi 21 (Omega), Python 3 (`xbmc.python 3.0.1`)
**Nutzer:** Nicht-Programmierer, bedient Kodi auf Android/Handy.

---

## Architektur-Entscheidungen

### TMDB: Direkte API, nicht TMDb Helper
Das Addon spricht **direkt** mit der TMDB REST API (`api.themoviedb.org`).
TMDb Helper kann keine Daten an andere Addons weitergeben – es ist kein nutzbarer Daten-Provider.
Der Nutzer braucht einen **kostenlosen API Key** von themoviedb.org (sofort, keine Wartezeit).

### Ablauf TMDB-Anreicherung
1. Stalker-API liefert Filmliste (Titel, interne IDs, Poster-URLs)
2. `lib/tmdb.py` sucht Titel bei TMDB → holt Poster, Fanart, Plot, Bewertung, Jahr
3. Ergebnis wird **30 Tage lokal gecacht** (minimiert API-Calls)
4. `lib/addon.py` baut den Kodi `ListItem` mit TMDB-Daten auf
5. Klick auf Film → startet direkt (kein Umweg über TMDb Helper)

### TMDb Helper Kompatibilität
`list_item.setProperty('tmdb_id', ...)` und `video_info.setUniqueID('tmdb', ...)` werden gesetzt,
damit TMDb Helper optional eigene Overlays/Details anzeigen kann. Pflicht ist es nicht.

---

## Wichtige Dateien

| Datei | Zweck |
|---|---|
| `lib/tmdb.py` | TMDB API Client + 30-Tage-Cache |
| `lib/addon.py` | Kodi ListItem-Aufbau, TMDB-Felder anwenden |
| `lib/api.py` | Stalker Middleware API Client |
| `lib/auth.py` | Stalker Authentifizierung / Token-Verwaltung |
| `resources/settings.xml` | Kodi Einstellungen (zwei Sections, gleiche Addon-ID) |
| `resources/language/resource.language.en_gb/strings.po` | String-IDs (32100–32107 = TMDB) |

---

## Performance – TMDB-Ladezeiten

### Was wird pro Film von TMDB geholt?
**Alle Felder kommen in einem einzigen HTTP-Request** (`/search/movie` oder `/search/tv`).
Es gibt keinen separaten Request pro Feld. Was zurückkommt:

| Feld | Wozu | Weglassbar? |
|---|---|---|
| `plot` | Beschreibungstext im Kodi-Info-Popup | Nein (Hauptnutzen) |
| `poster` | Hochwertiges Poster (500px) | Nein (Hauptnutzen) |
| `fanart` | Hintergrundbild (1280px) | Ja – spart Bandbreite, nicht API-Zeit |
| `rating` | Bewertung z.B. 7.4 | Ja |
| `votes` | Anzahl Stimmen z.B. 12345 | Ja (kaum sichtbar) |
| `year` | Erscheinungsjahr | Ja – kommt oft schon von Stalker |
| `tmdb_id` | Für TMDb Helper Kompatibilität | Ja – nur nötig wenn TMDb Helper genutzt wird |

**Fazit:** Einzelne Felder weglassen spart **keine** Ladezeit – der API-Call dauert gleich lang.

### Warum dauert es so lange (erste Seite)?

| Situation | Dauer pro Film | Dauer 20 Filme |
|---|---|---|
| Kein Cache (erste Nutzung) | ~200–500 ms | **~4–10 Sekunden** |
| Cache vorhanden (nächster Besuch) | ~1 ms | < 1 Sekunde |
| Netzwerk-Timeout (TMDB offline) | 10 Sekunden | hängt ewig |

Der Cache hält 30 Tage. Nach dem ersten Laden einer Kategorie ist alles schnell.

### Performance-Bug: Singleton-Fix (`_get_tmdb_client`)

**Problem (alt):** `_get_tmdb_client()` wurde für **jeden Film** neu aufgerufen.
Jeder Aufruf erstellte eine neue `TmdbClient`-Instanz → Cache-Datei wurde 20x von Disk gelesen
und 20x zurückgeschrieben (JSON serialize/deserialize für jede Datei-Operation).

**Fix:** Modul-globaler Singleton in `lib/addon.py`:
```python
_tmdb_client_singleton = None

def _get_tmdb_client():
    global _tmdb_client_singleton
    cfg = G.tmdb_config
    if not cfg.enabled or not cfg.api_key:
        return None
    if _tmdb_client_singleton is None:
        _tmdb_client_singleton = TmdbClient(cfg.api_key, cfg.language)
    return _tmdb_client_singleton
```
Kodi startet das Plugin als **neuen Prozess** pro Navigation → der Singleton lebt nur für eine
Seiten-Darstellung (z.B. 20 Filme). Das ist genau richtig: Cache 1x laden, 20x nutzen.

**Ergebnis:** Cache-Disk-I/O reduziert von 40 Operationen auf 1 Lese- + N Schreib-Operationen.

### Performance-Fix 2: Batch-Flush (`flush()`)

**Problem (alt):** `__to_cache()` rief sofort `__persist_cache()` auf → 1 Disk-Write pro Film.
Bei 20 Filmen, von denen 20 neu sind: 20 Schreiboperationen auf dieselbe JSON-Datei.

**Fix:** `__to_cache()` schreibt nur noch in den In-Memory-Dict.
Neues `flush()`-Method schreibt einmalig am Ende des Listings.
`addon.py` ruft `tmdb.flush()` auf direkt vor `endOfDirectory()`.

```python
# tmdb.py
def flush(self):
    if self.__cache_loaded:
        self.__persist_cache()

def __to_cache(self, key, data):
    self.__cache[key] = {'data': data, 'ts': time.time()}
    # Kein persist hier – wird von flush() am Ende gemacht
```

**Warum nicht "beim Film-Schauen" schreiben?**
Kodi startet für jede Navigation einen **neuen Prozess**. Listing und Playback sind völlig
getrennte Prozesse. Am Prozessende geht der RAM verloren. Es ist technisch unmöglich, Daten
aus dem Listing-Prozess in den späteren Play-Prozess zu übertragen.

**Ergebnis:** N Schreib-Ops → 1 Schreib-Op pro Listing. Bei 20 neuen Filmen: 19 Writes gespart.

### Vergleich alternativer Metadaten-Anbieter

| Anbieter | Geschwindigkeit | Kosten | Qualität | Kodi-tauglich? |
|---|---|---|---|---|
| **TMDB** (aktuell) | ~200–500ms | Kostenlos | Sehr gut, viele Sprachen | Ja, Standard |
| OMDb (IMDb-basiert) | ~200–400ms | Kostenlos (1000/Tag) | Gut, weniger nicht-EN | Ja |
| Trakt.tv | ~300–600ms | Kostenlos | Gut, kein Fanart | Ja |
| MDBList | ~100–300ms | Kostenlos bis Limit | Aggregiert mehrere Quellen | Ja |

**Fazit:** TMDB ist die richtige Wahl. Andere Anbieter sind nicht wesentlich schneller.
Der Flaschenhals ist die Netzwerklatenz, nicht der Anbieter selbst.

### FSK-Altersfreigaben von TMDB holen

TMDB hat Altersfreigaben (DE = FSK), aber **nicht im Such-Endpunkt** (`/search/movie`).
Es wäre ein **zweiter API-Call** nötig: `/movie/{id}/release_dates`.

**Ablauf mit FSK:**
1. `/search/movie` → Titel finden, `id` holen (~300ms)
2. `/movie/{id}?append_to_response=release_dates` → FSK aus DE-Zertifizierung lesen (~300ms)

Das würde die Ladezeit für unkachet Filme verdoppeln (~600ms statt ~300ms pro Film).
→ Vorerst nicht implementiert. Bei Bedarf als optionales Setting umsetzbar.

---

## Bekannte Bugs & Fixes (heute gelöst)

### 1. `setRating()` TypeError
**Problem:** `video_info.setRating(float(rating), type='tmdb', defaultt=True)` → TypeError
**Ursache:** Falsche Argument-Reihenfolge + Kodi akzeptiert `defaultt` nicht als Keyword-Argument
**Fix:** Positionsargumente in korrekter Reihenfolge + try/except:
```python
try:
    video_info.setRating('tmdb', float(info['rating']), info.get('votes', 0), True)
except TypeError:
    pass
```
Kodi API Signatur: `setRating(type, rating, votes=0, defaultt=False)`

### 2. Doppeltes `.tmdb` in settings.xml Section-ID
**Problem:** Nach einem replace-all entstand `id="plugin.video.stalkervod.tmdb.tmdb"`
**Fix:** Zweite Section-ID korrigiert auf `plugin.video.stalkervod.tmdb`

---

## Build & Packaging

```bash
make package   # Erstellt saubere Kodi-ZIP (ohne Tests, ohne .git, ohne dev-Dateien)
# Ergebnis: build/plugin.video.stalkervod.tmdb-0.0.1.zip
```

**Was in der ZIP landet:** `addon.xml`, `*.py`, `lib/`, `resources/`, `LICENSE`, `README.md`
**Was NICHT rein kommt:** `.git/`, `Makefile`, `upstream_source/`, `pyproject.toml`, `requirements.txt`

**Kodi-Anforderung:** ZIP muss einen Ordner enthalten der exakt wie die Addon-ID heißt:
```
plugin.video.stalkervod.tmdb/
├── addon.xml
├── addon_entry.py
...
```

**Für den Nutzer zum Download:** `dist/plugin.video.stalkervod.tmdb-0.0.1.zip` (im Repo, tracked)
`build/` ist in `.gitignore` – nur `dist/` wird committed.

---

## Einstellungen (settings.xml)

| Setting-ID | Typ | Bedeutung |
|---|---|---|
| `tmdb_enabled` | boolean | TMDB-Anreicherung ein/aus |
| `tmdb_api_key` | string (hidden) | Kostenloser Key von themoviedb.org |
| `tmdb_language` | string | Sprache für Metadaten, default `de-DE` |

Die `settings.xml` hat **zwei `<section>`-Blöcke** mit der gleichen `id="plugin.video.stalkervod.tmdb"` –
das ist in Kodi valide, die Sections sind visuelle Gruppierungen.

---

## Für den nächsten Merge / nächste Session

- Branch: `claude/stalker-vod-kodi-21-8QE5L`
- Alle Commits sind gepusht
- ZIP für direkten Download: `dist/plugin.video.stalkervod.tmdb-0.0.1.zip`
- Nach dem Merge: `dist/` ZIP bei neuen Versionen aktualisieren (`make package` + `cp build/*.zip dist/`)

### Offene Verbesserungs-Ideen (noch nicht umgesetzt)

| Idee | Aufwand | Effekt |
|---|---|---|
| `fanart`/`votes` weglassen (optional per Setting) | mittel | weniger Kodi-Bandbreite |
| Timeout für TMDB-Calls kürzen (aktuell 10s → 3s) | klein | hängt nicht 10s bei Offline-TMDB |
| FSK-Altersfreigaben (zweiter API-Call pro Film nötig) | mittel | verdoppelt Ladezeit bei leerem Cache |
| Parallele TMDB-Requests (Threading) | groß | deutlich schneller beim ersten Laden |
