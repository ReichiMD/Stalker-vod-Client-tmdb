# CLAUDE.md – Projektnotizen für KI-Assistenten

## Projektübersicht

Fork von `plugin.video.stalkervod` v1.2.0 (rickeylohia, GPL-3.0).
Erweitert um direkte TMDB-Metadaten-Integration (Poster, Fanart, Plot, Bewertung).

**Addon-ID:** `plugin.video.stalkervod.tmdb`
**Zielplattform:** Kodi 21 (Omega), Python 3 (`xbmc.python 3.0.1`)
**Nutzer:** Nicht-Programmierer, bedient Kodi auf Android/Handy.

---

## PFLICHT am Sitzungsende – ZIP-Release erstellen

> **WICHTIG:** Nach JEDER Session, in der Code geändert wurde, MUSS vor dem letzten Commit:
> 1. Die Versionsnummer in `addon.xml` erhöht werden (Patch: z.B. 0.0.3 → 0.0.4)
> 2. Ein News-Eintrag in `addon.xml` unter `<news>` hinzugefügt werden (Datum + Was wurde geändert)
> 3. `make package` ausführen → erstellt `build/plugin.video.stalkervod.tmdb-X.X.X.zip`
> 4. Alte ZIP aus `dist/` löschen, neue ZIP nach `dist/` kopieren
> 5. `addon.xml` + `dist/*.zip` in denselben Commit aufnehmen

```bash
# Schritt 3–4 als Einzeiler:
make package && rm -f dist/*.zip && cp build/plugin.video.stalkervod.tmdb-*.zip dist/
```

**Warum:** Der Nutzer ist Nicht-Programmierer. Die ZIP in `dist/` ist die einzige Möglichkeit,
das Addon herunterzuladen und in Kodi zu installieren. Ohne aktuelle ZIP ist die Session wertlos.

> **PFLICHT nach Schritt 4:** Nach jeder ZIP-Erstellung auch die `CLAUDE.md` aktualisieren:
> - Abschnitt "Für den nächsten Merge / nächste Session" → Branch, Version, ZIP aktualisieren
> - Tabelle "Zuletzt umgesetzte Features" → neue Features eintragen
> - Bekannte Bugs/Fixes die in dieser Session gelöst wurden → eintragen

---

## ⚠️ KODI 21 (OMEGA) – PFLICHT-WISSEN

> **Vor dem Coden IMMER zuerst `KODI_SETTINGS_REFERENCE.md` lesen!**
> Dort sind alle korrekten Syntax-Beispiele mit Erklärungen hinterlegt.
> Ohne diesen Spickzettel entstehen unsichtbare UI-Elemente ohne Fehlermeldung.

### Kurzübersicht der häufigsten Fallen

| Fehler | Fix | Details in |
|---|---|---|
| Button unsichtbar | `<data>` statt `<action>`, `format="action"` am Control | KODI_SETTINGS_REFERENCE.md §2 |
| Spinner unsichtbar | `format="integer"` statt `subtype="integer"` | KODI_SETTINGS_REFERENCE.md §4 |
| Nur Pfeile statt Dropdown | `type="list"` statt `type="spinner"` am Control | KODI_SETTINGS_REFERENCE.md §3b/§4 |
| API-Key/Passwort sichtbar | `<hidden>true</hidden>` als Kind-Element in `<control>` | KODI_SETTINGS_REFERENCE.md §6a |
| Ausgrauen klappt nicht | `<dependencies>` Block statt alter `<enable>eq(...)` Syntax | KODI_SETTINGS_REFERENCE.md §7 |
| String fehlt / leer | Beide .po-Dateien pflegen (en_gb + de_de) | KODI_SETTINGS_REFERENCE.md §9 |
| Setting nach Klick auf "Schließen" noch aktiv | `<close>true</close>` in Action-Settings | KODI_SETTINGS_REFERENCE.md §2 |

### REGEL: `onSettingsChanged` wird bei JEDER Einstellungsänderung aufgerufen

Nicht nur bei der Ersteinrichtung. Jede Änderung einer beliebigen Einstellung feuert diesen
Callback. Deshalb ist die **genaue Reihenfolge der Prüfungen** wichtig:

```python
def onSettingsChanged(self):
    addon = xbmcaddon.Addon()
    # 1. Zuerst: Ersteinrichtungs-Check (nur wenn Server + MAC gesetzt und Flag nicht da)
    ...
```

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
| **`KODI_SETTINGS_REFERENCE.md`** | **Spickzettel: korrekte settings.xml Syntax für Kodi 21 – VOR dem Coden lesen!** |
| `lib/tmdb.py` | TMDB API Client + 30-Tage-Cache |
| `lib/addon.py` | Kodi ListItem-Aufbau, TMDB-Felder anwenden |
| `lib/api.py` | Stalker Middleware API Client |
| `lib/auth.py` | Stalker Authentifizierung / Token-Verwaltung |
| `resources/settings.xml` | Kodi Einstellungen (vier Sections, gleiche Addon-ID) |
| `resources/language/resource.language.en_gb/strings.po` | String-IDs (32001–32168) – immer parallel in `de_de/strings.po` pflegen! |
| `resources/language/resource.language.de_de/strings.po` | Deutsche Übersetzung aller Strings – Kodi lädt sie automatisch bei dt. Sprache |

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

## Laden-Strategie & Cache-System

### Übersicht: Einstellungen im Abschnitt [Daten laden] und [Portal-Cache]

| Setting-ID | Typ | Standard | Bedeutung |
|---|---|---|---|
| `cache_enabled` | boolean | `true` | Lokalen Stalker-Cache verwenden (ja/nein) |
| `page_size` | integer (Dropdown) | `2` | Filme pro Seite: 1 (~20), 2 (~40), 5 (~100), 9999 (Alle auf einmal) |
| `stalker_cache_days` | integer (Dropdown) | `30` | Cache-Gültigkeitsdauer: 1 Monat (30 Tage), 3 Monate (90 Tage), Nie löschen |
| `update_new_data` | action | – | Portal-Daten in den Cache laden (smart: nur neue hinzufügen) |

---

### Verhaltensmatrix: `cache_enabled` × `page_size`

| `cache_enabled` | `page_size` | Ergebnis beim Ordner öffnen |
|---|---|---|
| AUS | 1 (Standard) | ~20 Filme vom Server, Weiter/Zurück-Schaltflächen |
| AUS | 2 (~40) | ~40 Filme vom Server, Weiter/Zurück-Schaltflächen |
| AUS | 5 (~100) | ~100 Filme vom Server, Weiter/Zurück-Schaltflächen |
| AUS | Alle | Alle Seiten vom Server auf einmal (langsam beim ersten Mal) |
| **EIN** | 1–5 | Seitenweise vom Server (Cache wird bei Paginierung nicht genutzt) |
| **EIN** | **Alle** | **Alle Filme sofort aus lokalem Cache ✓** (falls Cache leer → alle Seiten vom Server) |

> **Empfehlung:** Cache EIN + Alle auf einmal = schnellste Nutzererfahrung nach dem ersten Refresh.
> Auf schwachen Geräten (z.B. Android-Stick, 1 GB RAM): Cache EIN + 2 oder 5 Seiten empfohlen.

**Wo gesetzt:** `globals.py::init_globals()` → `self.addon_config.max_page_limit` und `self.addon_config.cache_enabled`

**Codelogik in `__list_vod` / `__list_series`:**
```python
load_all = G.addon_config.max_page_limit >= 9999   # page_size=9999 (Alle auf einmal)
use_cache = G.addon_config.cache_enabled
if load_all and use_cache and not search_term.strip() and fav == '0':
    cached = StalkerCache(...).get_videos(...)
    if cached:
        videos = {'data': cached, ...}   # sofort aus Cache
if videos is None:
    videos = Api.get_videos(...)         # Fallback: Server
```

---

### "Portal-Daten in den Cache laden" (`update_new_data`)

**Ein Button für alles:** Ersetzt die früheren zwei Buttons (`refresh_all_data` + `update_new_data`).
Verhält sich smart: Wenn der Cache leer ist, werden alle Daten geladen. Wenn bereits Daten
vorhanden sind, werden nur neue Inhalte hinzugefügt. Vorhandene Daten bleiben immer erhalten.

**Implementiert in:** `addon.py::__update_new_data()` (Button im Portal-Cache Bereich)

**Ablauf:**
1. Öffnet `xbmcgui.DialogProgress()` mit Abbrechen-Schaltfläche
2. Lädt alle VOD- + alle Series-Kategorien vom Server → speichert in Stalker-Cache
3. Wendet Ordner-Filter an (nur sichtbare Kategorien werden verarbeitet)
4. Für jede Kategorie: Serverliste holen → mit Cache vergleichen (nach `id`)
5. **Nur neue Filme** → werden dem Cache vorangestellt (erscheinen oben)
6. Cache-Zeitstempel wird auch bei Kategorien ohne neue Inhalte aktualisiert
7. Falls TMDB aktiv: TMDB-Lookup nur für die neuen Filme → `tmdb.flush()`
8. Vorhandene Filme + TMDB-Daten bleiben **unverändert**
9. Zeigt am Ende: „X neue Inhalte hinzugefügt."

**Silent-Modus:** `?action=update_new_data&silent=1` → kein Dialog (für Hintergrundnutzung durch Service).
**Wenn TMDB nicht konfiguriert:** TMDB-Schritt wird einfach übersprungen – kein Fehler.

---

### Automatischer Hintergrund-Refresh (Service)

Der `BackgroundService.run()` prüft beim Kodi-Start ob der Stalker-Cache abgelaufen ist.
Die Gültigkeitsdauer ist konfigurierbar über `stalker_cache_days` (Standard: 30 Tage / 1 Monat).
Falls abgelaufen → startet `update_new_data` im Silent-Modus lautlos im Hintergrund.

**Respektiert `cache_enabled`:** Wenn der Nutzer den Cache deaktiviert hat, wird der
automatische Refresh nicht ausgelöst.
**Respektiert `stalker_cache_days=0` (Nie ablaufen):** Kein automatischer Refresh.

**Prüfung:** `StalkerCache(profile, cache_days=X).categories_are_stale('vod')` → vergleicht Datei-Timestamp.

---

### Lokaler Stalker-Cache (`lib/stalker_cache.py`)

| Inhalt | Datei | Gültigkeit |
|---|---|---|
| VOD-Kategorien | `stalker_cats_vod.json` | konfigurierbar (Standard: 1 Monat) |
| Series-Kategorien | `stalker_cats_series.json` | konfigurierbar (Standard: 1 Monat) |
| VOD-Videos (pro Kategorie) | `stalker_videos_vod_{id}.json` | konfigurierbar (Standard: 1 Monat) |
| Series-Videos (pro Kategorie) | `stalker_videos_series_{id}.json` | konfigurierbar (Standard: 1 Monat) |

Alle Dateien liegen in `{kodi_profile}/plugin.video.stalkervod.tmdb/`.
Gültigkeitsdauer wird über `stalker_cache_days` konfiguriert (1 Monat, 3 Monate, Nie löschen).
`StalkerCache(cache_dir, cache_days=N)` akzeptiert den Parameter. `cache_days=0` → nie löschen.

---

## Such-Verhalten (Search)

### VOD SEARCH / SERIES SEARCH (Top-Level-Klick)
- Kein Gruppenauswahl-Dialog – sofort Tastatur erscheint mit Heading "Alle Kategorien"
- Sucht **parallel** in allen sichtbaren (gefilterten) Gruppen per `__search_vod_across_categories()`
- Ergebnisse aus allen Gruppen werden kombiniert und als ein Listing angezeigt
- Pagination ist deaktiviert (max_page_items=9999 intern), alle Ergebnisse auf einmal
- Implementiert in: `lib/addon.py::__search_vod` → `__search_vod_across_categories`
- Analog für Serien: `__search_series` → `__search_series_across_categories`
- Analog für TV: `__search_tv` → `__search_tv_across_genres`

### Kontextmenü-Suche (Rechtsklick auf Gruppe → "Search")
- `params['category']` und `params['category_id']` sind bereits gesetzt
- Sucht **nur** in der gewählten Gruppe (serverseitig über `Api.get_videos(category_id, ...)`)
- Verhält sich wie ein normales Listing mit Suchbegriff

### Warum ist die Gruppen-Auswahl weg?
Der Nutzer möchte nie erst eine Gruppe auswählen – die Filterung übernimmt bereits der
Ordner-Filter in den Einstellungen. Die Suche soll einfach "über alles Sichtbare" gehen.

---

## Filter-Funktion (Genre / Jahr / Bewertung)

### Übersicht
"VOD FILTER" und "SERIES FILTER" Buttons in der Ordner-Ansicht (neben SEARCH).
Filtern komplett auf Basis von TMDB-Cache-Daten – **kein einziger zusätzlicher API-Call**.

### Voraussetzungen
- TMDB aktiviert + API-Key vorhanden
- TMDB-Daten wurden synchronisiert (mindestens einmal "Alle Daten aktualisieren")
- Button erscheint nur wenn TMDB aktiviert ist

### Verfügbare Filter-Kriterien (Phase 1 – aus 1. API-Abruf)

| Kriterium | Dialog-Typ | Logik |
|---|---|---|
| Genre | `multiselect()` | Film hat mindestens EIN gewähltes Genre |
| Jahr/Dekade | `select()` (Dekaden) | Film fällt in gewählten Zeitraum |
| Mindestbewertung | `select()` (9+, 8+, 7+, 6+, 5+) | Film hat mindestens X Sterne |

### Kombinations-Filter ("Alle Kriterien")
Alle drei Filter werden nacheinander abgefragt und mit **UND-Logik** verknüpft.
Beispiel: Genre=Action + Jahr=2020-2029 + Rating=7+ → zeigt nur gute aktuelle Action-Filme.

### Technischer Ablauf
1. Alle Videos aus Stalker-Cache laden (alle sichtbaren Kategorien)
2. Für jedes Video: TMDB-Cache-Lookup via `get_cached_movie_info()` / `get_cached_tv_info()`
3. Einzigartige Genres/Jahre/Ratings sammeln
4. Filter-Dialog(e) anzeigen
5. Videos filtern, Ergebnis als flache Liste anzeigen (wie Suche)

### Implementiert in
- `lib/tmdb.py`: `get_cached_movie_info()`, `get_cached_tv_info()` (Cache-only, kein API-Call)
- `lib/addon.py`: `__vod_filter()`, `__series_filter()`, `__run_filter()`,
  `__collect_filter_data()`, `__ask_genre_filter()`, `__ask_year_filter()`,
  `__ask_rating_filter()`, `__apply_filters()`, `__build_filter_desc()`

### Phase 2 (geplant): Erweiterte Daten vom 2. API-Abruf
- FSK-Altersfreigaben via `/movie/{id}/release_dates` (verdoppelt Sync-Zeit)
- Settings-Gruppe "Erweiterte Daten (2. Abruf pro Film)" im TMDB-Tab bereits vorbereitet
- Filter-Dialog würde dann FSK als 4. Kriterium hinzufügen

---

## Ersteinrichtungs-Dialog – DEAKTIVIERT (v0.2.9)

**Status:** Der automatische Ersteinrichtungs-Dialog wurde in v0.2.9 deaktiviert.

**Grund:** Es macht keinen Sinn, sofort alle Daten vom Portal zu laden, bevor der Nutzer
die Ordner-Filter konfiguriert hat. Es sind zu viele Daten und das dauert unnötig lange.

**Stattdessen:** Der Nutzer soll:
1. Server + MAC-Adresse eingeben
2. Ordner-Filter konfigurieren (Portal Einstellung → Ordner-Filter)
3. Manuell "Alle Daten aktualisieren" klicken (Portal Einstellung → Daten aktualisieren)

Die Flag-Datei `initial_setup_done` wird nicht mehr erstellt oder geprüft.
Der tägliche Hintergrund-Refresh (`_check_daily_cache_refresh`) bleibt aktiv und
erneuert den Cache automatisch nach 24h (respektiert Ordner-Filter).

---

## Bekannte Bugs & Fixes (heute gelöst)

### 3. Einstellungen wirken erst nach Kodi-Neustart (v0.2.0 behoben)
**Problem:** Änderungen an Einstellungen (z.B. TMDB aktivieren, API-Key, Poster/Fanart an/aus,
Ordner-Filter, Portal-Adresse) hatten keine Wirkung ohne Kodi-Neustart.
**Ursache:** `addon.xml` hat `<reuselanguageinvoker>true</reuselanguageinvoker>` – Kodi
wiederverwendet denselben Python-Prozess für mehrere Navigationen. In `globals.py::init_globals()`
standen ALLE `getSetting()`-Aufrufe innerhalb eines `if self.__is_addd_on_first_run:`-Guards,
der beim zweiten Aufruf (selber Prozess) nicht mehr ausgeführt wurde. Einstellungen wurden
damit nur einmal beim Prozessstart gelesen.
**Fix:** Alle `getSetting()`-Aufrufe (und `handle = int(sys.argv[1])`) aus dem First-Run-Guard
herausgezogen. Sie werden jetzt bei **jedem** `init_globals()`-Aufruf neu gelesen. Nur echte
statische Info (addon_id, name, Pfad, token_path-Erstellung) verbleibt im Guard.
Zusätzlich: `_tmdb_client_singleton` in `addon.py::run()` wird jetzt bei jedem Aufruf zurückgesetzt,
damit TMDB-Setting-Änderungen (Key, Sprache) sofort einen neuen Client erzeugen.

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

Die `settings.xml` hat **drei `<section>`-Blöcke** mit der gleichen `id="plugin.video.stalkervod.tmdb"` –
das ist in Kodi valide, die Sections sind visuelle Tabs/Kategorien.

### Tab 1: Portal Login
Reine Anmeldedaten für den Stalker-Server.

| Setting-ID | Typ | Bedeutung |
|---|---|---|
| `server_address` | string | Stalker-Server-URL |
| `alternative_context_path` | boolean | `/portal.php` statt `/server/load.php` |
| `mac_address` | string | MAC-Adresse des Geräts |
| `serial_number` | string | Seriennummer |
| `device_id` | string | Geräte-ID 1 |
| `device_id_2` | string | Geräte-ID 2 |
| `signature` | string | Signatur |

### Tab 2: Portal Einstellung
Alles was das Portal-Verhalten steuert: Filter, Cache, Datenaktualisierung.

**Gruppe: Ordner-Filter**

| Setting-ID | Typ | Standard | Bedeutung |
|---|---|---|---|
| `folder_filter_mode` | integer (Dropdown) | `0` | 0=Alle anzeigen, 1=Stichwort-Filter, 2=Manuelle Auswahl |
| `folder_filter_keywords` | string | `de, deutsch, german, multi` | Kommagetrennte Stichwörter (nur aktiv bei Modus=1) |
| `folder_filter_select_vod` | action | – | VOD-Ordner auswählen (nur aktiv bei Modus=2) |
| `folder_filter_select_series` | action | – | Serien-Ordner auswählen (nur aktiv bei Modus=2) |
| `folder_filter_select_tv` | action | – | TV-Genres auswählen (nur aktiv bei Modus=2) |

> **Filter-Modus als Dropdown:** Ersetzt die alten zwei Toggles (`folder_filter_use_keywords` +
> `folder_filter_use_manual`). Ein Dropdown macht es unmöglich beide gleichzeitig zu aktivieren.
> `globals.py` wandelt den Integer in die bestehenden `FilterConfig.use_keywords`/`use_manual`
> Booleans um → der Rest des Codes bleibt unverändert.

**Gruppe: Anzeige**

| Setting-ID | Typ | Standard | Bedeutung |
|---|---|---|---|
| `remove_lang_tags` | boolean | `true` | Sprachkürzel aus Ordner-/Filmnamen entfernen |
| `remove_lang_keywords` | string | `de, en, nl, fr, it, es, pl, tr, ru, pt, ar, multi, deutsch, german` | Kommagetrennte Kürzel die entfernt werden (nur aktiv bei Toggle=an) |

> **Zwei Muster werden erkannt:**
> - Präfix: `de - Action` → `Action` (Sprachcode + Bindestrich am Anfang)
> - Suffix: `Hulk (DE)` oder `Hulk [DE]` oder `Hulk - DE` → `Hulk` (Sprachcode am Ende)
> Groß-/Kleinschreibung wird ignoriert. Wenn nach dem Entfernen ein leerer String übrig bleibt,
> wird der Original-Name beibehalten. Verbessert auch TMDB-Trefferquote.

**Gruppe: Daten laden**

| Setting-ID | Typ | Standard | Bedeutung |
|---|---|---|---|
| `cache_enabled` | boolean | `true` | Lokalen Cache verwenden (aus = immer Server) |
| `page_size` | integer (Dropdown) | `2` | Filme pro Seite: Standard (~20), 2 Seiten (~40), 5 Seiten (~100), Alle auf einmal |

**Gruppe: Portal-Cache**

| Setting-ID | Typ | Bedeutung |
|---|---|---|
| `stalker_cache_days` | integer (Dropdown) | Cache-Gültigkeitsdauer: 1 Monat (Standard), 3 Monate, Nie löschen |
| `stalker_show_cache_info` | action | Cache-Statistiken anzeigen (Kategorien, Filme, Größe, Alter) |
| `update_new_data` | action | Portal-Daten in den Cache laden (smart: vorhandene bleiben, neue werden hinzugefügt) |
| `stalker_clear_cache` | action | Portal-Cache komplett löschen (mit Bestätigungsdialog) |

### Tab 3: TMDB
| Setting-ID | Typ | Bedeutung |
|---|---|---|
| `tmdb_enabled` | boolean | TMDB-Anreicherung ein/aus |
| `tmdb_api_key` | string (hidden) | Kostenloser Key von themoviedb.org |
| `tmdb_language` | string | Sprach-Code für Metadaten, default `de-DE` |

> **Hinweis:** Alle Aktions-Settings (`refresh_all_data`, `update_new_data`,
> `folder_filter_select_*`, `tmdb_refresh_now`, `tmdb_clear_cache`, `tmdb_show_cache_info`)
> sind `type="action"` mit `<data>RunPlugin(...)</data>` + `<control type="button" format="action" />`.

---

## Für den nächsten Merge / nächste Session

- Branch: `claude/fix-filter-cache-settings-IKQX4`
- Alle Commits sind gepusht
- ZIP für direkten Download: `dist/plugin.video.stalkervod.tmdb-0.3.3.zip`
- ZIP-Erstellung ist jetzt Pflicht am Sitzungsende (siehe Abschnitt oben)
- **Nach ZIP-Erstellung immer auch CLAUDE.md aktualisieren** (diese Datei!)

### Zuletzt umgesetzte Features

| Feature | Branch | Beschreibung |
|---|---|---|
| Portal-Cache wie TMDB-Cache | `claude/fix-filter-cache-settings-IKQX4` | Portal-Cache-Gültigkeitsdauer an TMDB-Cache angeglichen: 1 Monat (30 Tage, neuer Standard), 3 Monate (90 Tage), Nie löschen. Alte Werte (1 Tag, 3 Tage, 1 Woche) werden automatisch auf den neuen Standard migriert. |
| Filter: "Alle" Option in Kombination | `claude/fix-filter-cache-settings-IKQX4` | Im Kombinations-Filter ("Alle Kriterien") wird jetzt bei Genre, Jahr und Bewertung ganz oben "Alle Genres" / "Alle Jahre" / "Alle Bewertungen" angezeigt. Damit kann man einzelne Kriterien überspringen ohne den ganzen Filter abzubrechen. |
| Filter: Kein Hängenbleiben mehr | `claude/fix-filter-cache-settings-IKQX4` | Wenn der Filter keine Ergebnisse findet oder der Nutzer abbricht, wird endOfDirectory korrekt aufgerufen. Vorher blieb Kodi im Ladebildschirm hängen. |
| Filme pro Seite (Dropdown) | `claude/brainstorm-improvements-ZpXPB` | Boolean-Toggle "Alle Filme auf einmal anzeigen" durch Dropdown "Filme pro Seite" ersetzt. 4 Optionen: Standard (~20), 2 Seiten (~40, bisheriger Standard), 5 Seiten (~100), Alle auf einmal. Schwache Geräte können kleinere Seitengrößen wählen. Keine Cache-Dependency mehr – Dropdown immer verfügbar. |
| Settings-Umbau Portal-Cache | `claude/portal-settings-cache-refactor-T3TRf` | "Alle Daten aktualisieren" + "Nur neue Inhalte" durch einen Button "Portal-Daten in den Cache laden" ersetzt. Smart: lädt alles beim ersten Mal, danach nur neue Inhalte. In die Portal-Cache-Gruppe verschoben. |
| Portal-Cache-Gültigkeitsdauer | `claude/portal-settings-cache-refactor-T3TRf` | Neues Dropdown: 1 Tag (Standard), 3 Tage, 1 Woche, Nie ablaufen. StalkerCache akzeptiert `cache_days` Parameter. Hintergrund-Service nutzt konfigurierte Gültigkeit. |
| Schalter-Umbenennung | `claude/portal-settings-cache-refactor-T3TRf` | "Alle Seiten auf einmal laden" → "Alle Filme auf einmal anzeigen" für bessere Verständlichkeit. |
| Smart Background Refresh | `claude/portal-settings-cache-refactor-T3TRf` | Hintergrund-Service nutzt jetzt Delta-Update (update_new_data) statt Full-Refresh. Schneller und erhält vorhandene Cache-Daten. Respektiert "Nie ablaufen" Setting. |
| Stalker-API Retry + Pause | `claude/disable-auto-fetch-startup-rrG00` | Portal-Requests mit try/except + Retry (3 Versuche, exp. Backoff). 100ms Pause zwischen Seiten in get_listing(). Verhindert stilles Überspringen von Kategorien bei Netzwerkproblemen. |
| Auto-Fetch Erststart deaktiviert | `claude/disable-auto-fetch-startup-rrG00` | Automatischer Datenabruf beim ersten Start entfernt. Nutzer soll zuerst Ordner-Filter konfigurieren. |
| Portal-Cache-Verwaltung | `claude/disable-auto-fetch-startup-rrG00` | Neue Gruppe "Portal-Cache" in Portal Einstellung mit Buttons "Cache-Info anzeigen" und "Portal-Cache löschen" (analog TMDB-Cache). |
| Bildschirmschoner-Schutz | `claude/disable-auto-fetch-startup-rrG00` | InhibitScreensaver(true) während Refresh/Update-Operationen. Verhindert Abbruch durch Nvidia Shield Bildschirmschoner. |
| VOD/Series-Filter | `claude/brainstorm-filter-options-fSBXE` | Neuer "FILTER"-Button in der VOD/Series-Ordneransicht (neben SEARCH). Filtert nach Genre (Multiselect), Jahr/Dekade oder Mindestbewertung. Kombinationsfilter: Genre + Jahr + Bewertung gleichzeitig mit UND-Logik. Arbeitet nur mit TMDB-Cache-Daten (0 Extra-API-Calls). TMDB-Settings umstrukturiert in "Basis-Daten (1 Abruf)" und "Erweiterte Daten (2. Abruf)" als Vorbereitung für FSK. |
| Sprachkürzel entfernen | `claude/remove-language-suffix-wWT0N` | Entfernt Sprachkürzel wie "de - " (Präfix) und "(DE)" (Suffix) aus Ordner- und Filmnamen. Standardmäßig aktiv. Konfigurierbar per Setting: Toggle + Freitextfeld für Keywords. Verbessert auch TMDB-Trefferquote (sucht "Hulk" statt "Hulk (DE)"). |
| Tab-Umbau: 4→3 Tabs | `claude/analyze-tmdb-settings-Jzezc` | "Portal" → "Portal Login", "Ordner-Filter" → "Portal Einstellung", Cache-Tab aufgelöst und in Portal Einstellung integriert. 3 Gruppen: Ordner-Filter, Daten laden, Daten aktualisieren. |
| Filter-Modus als Dropdown | `claude/analyze-tmdb-settings-Jzezc` | Zwei Toggles (`folder_filter_use_keywords` + `folder_filter_use_manual`) durch ein Dropdown `folder_filter_mode` ersetzt (0=Alle, 1=Stichwort, 2=Manuell). Unmöglich beide gleichzeitig zu aktivieren. Dependencies grauen irrelevante Settings aus. globals.py wandelt Integer in bestehende Booleans um → addon.py unverändert. |
| load_all_pages nur bei Cache | `claude/analyze-tmdb-settings-Jzezc` | "Alle Seiten auf einmal laden" ist jetzt ausgegraut wenn "Lokalen Cache verwenden" aus ist. Dependency: `cache_enabled==true`. |
| Spickzettel KODI_SETTINGS_REFERENCE.md | `claude/review-addon-settings-docs-uVHz3` | Neue Datei mit verifizierten Syntax-Beispielen für alle settings.xml Control-Typen in Kodi 21. CLAUDE.md verweist darauf. Alte Syntax-Blöcke aus CLAUDE.md entfernt. |
| Sprach-Dropdown statt Freitextfeld | `claude/review-addon-settings-docs-uVHz3` | `tmdb_language` ist jetzt ein Spinner mit 9 Sprachen (de-DE, en-US, en-GB, fr-FR, it-IT, es-ES, nl-NL, pl-PL, tr-TR). Neue String-IDs 32160–32168 in beiden .po-Dateien. |
| `<dependencies>` Syntax überall | `claude/review-addon-settings-docs-uVHz3` | Alle alten `<enable>eq(...)` und `<enable>eq(-1,true)</enable>` Syntax durch korrekte `<dependencies><dependency type="enable">` Blöcke ersetzt. Alle TMDB-Settings werden beim Deaktivieren korrekt ausgegraut. |
| `<close>true</close>` bei Refresh-Buttons | `claude/review-addon-settings-docs-uVHz3` | "Alle Daten aktualisieren", "Nur neue Inhalte", "TMDB-Metadaten aktualisieren" schließen Einstellungen automatisch bevor der Fortschrittsbalken erscheint. |
| Ja/Nein-Dialog bei Cache löschen | `claude/review-addon-settings-docs-uVHz3` | Vor dem Löschen des TMDB-Caches erscheint eine Bestätigungsabfrage. Verhindert versehentliches Löschen. |
| API-Key maskiert (Sternchen) | `claude/analyze-tmdb-settings-Jzezc` | `<hidden>true</hidden>` als Kind-Element in `<control>` – API-Key wird mit `****` angezeigt. Vorher fälschlich im Klartext (hidden war als Attribut entfernt worden). |
| Dropdown statt Spinner | `claude/analyze-tmdb-settings-Jzezc` | `tmdb_language` und `tmdb_cache_days` nutzen jetzt `type="list"` statt `type="spinner"` – Popup-Liste mit allen Optionen statt nur Pfeile. |
| Spickzettel: §3b, §4, §6a neu | `claude/analyze-tmdb-settings-Jzezc` | KODI_SETTINGS_REFERENCE.md um `type="list"` (Dropdown vs Spinner) und `<hidden>true</hidden>` (Passwort-Maskierung) ergänzt. Fehler-Checkliste erweitert. |
| Echte Buttons in Einstellungen | `claude/review-addon-settings-docs-uVHz3` | Alle "Aktion"-Toggles durch echte `type="action"` Buttons ersetzt. Korrekte `version="1"` Syntax: `<data>` + `<control type="button" format="action"/>`. Toggle-Erkennungscode aus service.py entfernt. CLAUDE.md Regeln 1+4 korrigiert. |
| TMDB-Negativcache-Bug-Fix | `claude/tmdb-cache-performance-Jb0xr` | Filme ohne TMDB-Treffer wurden trotz Cache-Eintrag bei jedem Ordner-Öffnen erneut live abgefragt. Sentinel-Objekt `_CACHE_MISS` unterscheidet jetzt "nicht im Cache" von "gecacht, kein Treffer". 3. Öffnen ist jetzt genauso schnell wie 2. |
| Settings-Reload-Fix | `claude/fix-settings-reload-786Qf` | Alle getSetting()-Aufrufe werden jetzt bei jeder Navigation neu ausgeführt (nicht nur beim ersten Prozessstart). Betrifft TMDB, Filter, Portal, Cache. TMDB-Singleton wird ebenfalls zurückgesetzt. |
| Auswahl: welche Infos anzeigen | `claude/tmdb-metadata-strategy-Dc4Wn` | Neue Gruppe "What to show" im TMDB-Tab mit 5 Toggles: Poster, Fanart, Plot, Rating, Genre. Alle standardmäßig aktiv. `TmdbConfig` hat 5 neue `use_*`-Felder; `_apply_tmdb_to_item()` wertet sie aus. |
| TMDB-Metadaten jetzt laden | `claude/tmdb-metadata-strategy-Dc4Wn` | Toggle `tmdb_refresh_now` im TMDB-Tab. Lädt TMDB-Daten nur für Filme im Stalker-Cache, ohne Stalker-Daten neu herunterzuladen. Überspringt bereits gecachte Filme. Mit Abbrechen-Knopf und Rate-Limit-Schutz. |
| TMDB-Cache löschen | `claude/tmdb-metadata-strategy-Dc4Wn` | Toggle `tmdb_clear_cache` löscht `tmdb_cache.json`. Daten werden beim nächsten Ordner-Öffnen neu heruntergeladen. |
| Cache-Gültigkeitsdauer (Tage) | `claude/tmdb-metadata-strategy-Dc4Wn` | Neues Setting `tmdb_cache_days` (Standard: 30). Nutzer kann selbst einstellen wie lange Daten gültig bleiben. `TmdbClient.__init__` akzeptiert `cache_days`-Parameter. |
| Cache-Info-Dialog | `claude/tmdb-metadata-strategy-Dc4Wn` | Toggle `tmdb_show_cache_info` öffnet Dialog mit: Anzahl Einträge, Alter neuester/ältester Eintrag, verbleibende Tage, Dateigröße. Liest direkt aus `tmdb_cache.json`. |
| TMDB Rate-Limiting | `claude/tmdb-metadata-strategy-Dc4Wn` | Max. 35 Anfragen / 10 Sekunden. Automatische Pause bei Bedarf. `_request_times`-Liste in `TmdbClient`. |
| Harter 429-Abbruch + Dialog | `claude/tmdb-metadata-strategy-Dc4Wn` | Nach 3 aufeinanderfolgenden HTTP-429: `_aborted=True`, klarer OK-Dialog. Toast beim normalen Browsen (1x pro Prozess). |
| Genre-Namen von TMDB | `claude/tmdb-metadata-strategy-Dc4Wn` | `/genre/movie/list` + `/genre/tv/list` einmalig laden, 30 Tage gecacht in `tmdb_cache.json`. `setGenres()` im ListItem. |
| Timeout 10s → 5s | `claude/tmdb-metadata-strategy-Dc4Wn` | Kürzerer Timeout reduziert Wartezeit bei TMDB-Problemen. |
| Cache-Abschnitt in Einstellungen | `claude/optimize-data-refresh-S8crk` | Neuer `[Cache]`-Abschnitt: `cache_enabled` (an/aus), `load_all_pages` (hierhin verschoben), `refresh_all_data` (alles neu), `update_new_data` (nur neue Inhalte). |
| Delta-Update (update_new_data) | `claude/optimize-data-refresh-S8crk` | Neuer Button: prüft auf neue Filme, fügt sie zum Cache hinzu, holt TMDB nur für neue Einträge. Vorhandene Daten bleiben erhalten. |
| load_all_pages + Cache | `claude/optimize-data-refresh-S8crk` | `load_all_pages=false` (Standard) = Variante 1: Paginierung vom Server (~20 pro Seite). `load_all_pages=true` = Variante 2: alle Filme sofort aus Cache (oder alle Seiten vom Server wenn kein Cache). |
| Lokaler Stalker-Cache | `claude/optimize-data-refresh-S8crk` | `lib/stalker_cache.py` – Kategorien + Videolisten werden 24h lokal gecacht (je eine JSON-Datei pro Kategorie). Öffnen eines Ordners beim 2. Mal ist sofort (<1s). |
| Täglicher Hintergrund-Refresh | `claude/optimize-data-refresh-S8crk` | Service prüft beim Kodi-Start ob Cache älter als 24h ist → startet `refresh_all&silent=1` lautlos im Hintergrund. |
| Refresh speichert Stalker-Daten | `claude/optimize-data-refresh-S8crk` | `refresh_all` ist jetzt auch ohne TMDB sinnvoll: speichert alle Videolisten in den lokalen Cache. |
| Silent-Modus für Refresh | `claude/optimize-data-refresh-S8crk` | `?action=refresh_all&silent=1` – kein Fortschrittsdialog, für Hintergrundnutzung. |
| Stichwort-Filter Wortgrenze-Fix | `claude/fix-vod-folder-issue-bUQtt` | `"de"` matchte als Teilstring auch `"nl-videoland"` → jetzt `\b`-Wortgrenzen per Regex |
| Such-Filter fix | `claude/fix-vod-search-filtering-Fk1Ti` | Suche direkt ohne Gruppenauswahl-Dialog – immer alle sichtbaren Gruppen |
| Gruppen-Filter in Suche | `claude/fix-vod-search-filtering-Fk1Ti` | Such-Dialog zeigte vorher ausgeblendete Gruppen an – jetzt gefiltert |
| `load_all_pages` Setting | `claude/tmdb-key-pagination-f4wb3` | Alle Server-Seiten auf einmal laden (TiviMate-Stil) |
| `refresh_all_data` Schalter | `claude/tmdb-key-pagination-f4wb3` | Schalter statt Button – Kodi 21 `version="1"` settings unterstützt `type="action"` mit `<action>`-Child nicht |
| Ersteinrichtungs-Dialog | `claude/tmdb-key-pagination-f4wb3` | `onSettingsChanged` im Service erkennt erste Anmeldedaten-Eingabe → Ja/Nein-Dialog → startet `refresh_all` |
| Deutsches UI | `claude/tmdb-key-pagination-f4wb3` | `resource.language.de_de/strings.po` – alle Settings auf Deutsch bei deutschem Kodi |

> **Kodi-21-Einschränkungen:** Siehe Abschnitt "⚠️ KODI 21 – BEKANNTE EINSCHRÄNKUNGEN" ganz oben.

### Offene Verbesserungs-Ideen (noch nicht umgesetzt)

| Idee | Aufwand | Effekt |
|---|---|---|
| Auth-Singleton (wie TMDB-Singleton) | klein | token.json wird aktuell pro API-Call neu gelesen – einmal pro Prozess reicht |
| Parallele TMDB-Requests beim Refresh (Threading) | groß | Refresh deutlich schneller (statt sequenziell) |

---

## Geplante Phasen: Filter-Erweiterungen

### Phase 1: Basis-Filter (Genre / Jahr / Bewertung) — FERTIG (v0.2.8)

**Status:** Umgesetzt und im Branch `claude/brainstorm-filter-options-fSBXE`.

- "VOD FILTER" / "SERIES FILTER" Buttons in den Ordner-Ansichten
- Filtert nach Genre (Multiselect), Jahr/Dekade, Mindestbewertung
- Kombinations-Filter "Alle Kriterien" (UND-Logik)
- Arbeitet nur mit vorhandenen TMDB-Cache-Daten (kein Extra-API-Call)
- Settings-Gruppe "Erweiterte Daten (2. Abruf)" im TMDB-Tab vorbereitet

---

### Phase 2: FSK-Altersfreigaben (2. API-Abruf) — GEPLANT

**Ziel:** FSK-Daten (z.B. FSK 0, FSK 6, FSK 12, FSK 16, FSK 18) von TMDB holen
und als 4. Filter-Kriterium anbieten.

**Warum ein 2. API-Abruf nötig ist:**
Der Such-Endpunkt `/search/movie` liefert **keine** Altersfreigaben.
Man braucht einen Detail-Endpunkt pro Film:
```
GET /movie/{tmdb_id}?append_to_response=release_dates&api_key=...
```
Für TV-Serien:
```
GET /tv/{tmdb_id}/content_ratings?api_key=...
```

**Ablauf beim Sync (wenn FSK aktiviert):**
1. `/search/movie` → TMDB-ID holen (wie bisher, 1. Abruf)
2. `/movie/{tmdb_id}?append_to_response=release_dates` → FSK aus `release_dates` extrahieren
3. Im `release_dates`-Array nach dem Land "DE" suchen → Feld `certification` lesen
4. Falls kein DE-Eintrag: Fallback auf "US" (MPAA Rating)
5. Ergebnis im TMDB-Cache speichern als neues Feld `certification`

**Parsing der TMDB-Antwort (release_dates):**
```python
# Antwort von /movie/{id}?append_to_response=release_dates
{
    "release_dates": {
        "results": [
            {
                "iso_3166_1": "DE",
                "release_dates": [
                    {"certification": "12", "type": 3}  # type 3 = Theatrical
                ]
            }
        ]
    }
}
# → certification = "12" → im Cache als "FSK 12" speichern
```

**Neue Dateien / Änderungen:**

| Datei | Änderung |
|---|---|
| `lib/tmdb.py` | Neue Methode `get_movie_certification(tmdb_id)` und `get_tv_certification(tmdb_id)`. Neues Feld `certification` im Cache-Dict. |
| `lib/tmdb.py` | `__parse_movie()` / `__parse_tv()` um `certification` erweitern (nur wenn 2. Abruf aktiv) |
| `lib/addon.py` | `__collect_filter_data()` sammelt auch `certification`-Werte |
| `lib/addon.py` | `__ask_fsk_filter()` – neuer Dialog: `select()` mit FSK-Stufen (0, 6, 12, 16, 18) |
| `lib/addon.py` | `__apply_filters()` bekommt 4. Parameter `max_fsk` |
| `lib/addon.py` | `__run_filter()` – FSK als 4. Option im Hauptmenü + im Kombinations-Filter |
| `lib/addon.py` | `__refresh_all_data()` und `__tmdb_refresh_now()` → 2. API-Call wenn Setting aktiv |
| `lib/globals.py` | `TmdbConfig` bekommt `use_certification: bool = False` |
| `resources/settings.xml` | Toggle "FSK-Altersfreigabe laden" in Gruppe "Erweiterte Daten" |
| `strings.po` (en+de) | Strings für FSK-Toggle, FSK-Filter-Dialog, FSK-Stufen |

**Settings-Toggle:**
```xml
<!-- In Gruppe "Erweiterte Daten (2. Abruf pro Film)" -->
<setting id="tmdb_use_certification" type="boolean" label="32183" help="32184">
    <level>0</level>
    <dependencies>
        <dependency type="enable">
            <condition operator="is" setting="tmdb_enabled">true</condition>
        </dependency>
    </dependencies>
    <default>false</default>
    <control type="toggle" />
</setting>
```

**Performance-Auswirkung:**
- Pro Film: ~300ms zusätzlich (2. HTTP-Request)
- Bei 2000 Filmen: ~10 Minuten extra beim ersten Sync
- Bereits gecachte Filme werden übersprungen (Cache-Key mit `tmdb_id`)
- Rate-Limiting greift wie gehabt (35 req/10s)

**Filter-Dialog mit FSK (Kombination):**
```
Filtern nach:
  → Genre
  → Jahr / Jahrzehnt
  → Mindestbewertung
  → FSK-Altersfreigabe          ← NEU
  → Alle Kriterien (Kombination)
```
Bei "Alle Kriterien": Genre → Jahr → Bewertung → FSK (4 Schritte).

**FSK-Auswahl-Dialog:**
```
Maximale Altersfreigabe:
  → FSK 0  (Alle Altersstufen)
  → FSK 6  (Ab 6 Jahren)
  → FSK 12 (Ab 12 Jahren)
  → FSK 16 (Ab 16 Jahren)
  → FSK 18 (Keine Jugendfreigabe)
  → Alle anzeigen
```
Logik: Film wird angezeigt wenn seine FSK ≤ gewählter Wert.
Beispiel: "FSK 12" → zeigt FSK 0, FSK 6 und FSK 12, aber nicht FSK 16/18.

**Offene Fragen für Phase 2:**
- Soll FSK beim normalen Browsen angezeigt werden (z.B. im Info-Dialog)?
- Soll es einen separaten "FSK nachladen"-Button geben (wie "TMDB-Metadaten aktualisieren")?
  → Empfehlung: Ja, Option B – nur nachladen wenn User explizit will
- Fallback wenn kein DE-Rating: US-Rating (MPAA) umrechnen? Oder leer lassen?

---

### Phase 3: Verbessertes Filter-UI (Custom Window) — IDEE

**Ziel:** Statt sequenzieller Dialoge ein einziges Filter-Fenster mit allen Kriterien gleichzeitig.

**Aktuell (Phase 1):**
```
Dialog 1: "Filtern nach?" → Genre / Jahr / Rating / Kombination
Dialog 2: Genre-Auswahl (Multiselect)
Dialog 3: Jahr-Auswahl
Dialog 4: Rating-Auswahl
→ Ergebnis
```
= Bis zu 4 Klicks bis zum Ergebnis.

**Ziel (Phase 3):**
```
┌─── Film-Filter ────────────────────────┐
│                                         │
│  Genre:      [Action, Thriller    ▾]   │
│  Jahr:       [2020 – 2029         ▾]   │
│  Bewertung:  [7+ (Gut)            ▾]   │
│  FSK:        [FSK 12              ▾]   │
│                                         │
│       [Anwenden]    [Zurücksetzen]      │
└─────────────────────────────────────────┘
```
= 1 Fenster, alles auf einen Blick, 1 Klick "Anwenden".

**Technisch:**
- `xbmcgui.WindowXMLDialog` mit eigenem XML-Layout
- XML-Datei: `resources/skins/Default/1080i/filter_dialog.xml`
- Braucht Custom-Controls: Buttons, Labels, Spinner/Listen
- Kodi-Skin-abhängig – muss mit Default-Skin (Estuary) funktionieren
- Deutlich aufwändiger als die Kodi-Standard-Dialoge

**Aufwand:** Groß (eigenes XML-Layout + Python-Controller-Klasse).
**Priorität:** Niedrig – die sequenziellen Dialoge funktionieren gut genug.
**Alternative:** Phase 1 weiter verbessern (z.B. letzten Filter merken, Zurück-Button).

---

### Übersicht: Was ist wo vorbereitet?

| Was | Wo | Status |
|---|---|---|
| Filter-Button in Ordner-Ansicht | `lib/addon.py` Zeile ~292, ~328 | Fertig |
| Filter-Logik (Genre/Jahr/Rating) | `lib/addon.py` `__run_filter()` etc. | Fertig |
| Cache-Only-Lookup | `lib/tmdb.py` `get_cached_movie_info()` / `get_cached_tv_info()` | Fertig |
| Settings: "Basis-Daten" Gruppe | `resources/settings.xml` group `tmdb_fields_group` | Fertig |
| Settings: "Erweiterte Daten" Gruppe | `resources/settings.xml` group `tmdb_extended_group` | Leer (nur Info-Text) |
| String-IDs bis 32187 | `strings.po` (en + de) | Belegt |
| Nächste freie String-ID | 32200 | Frei (32194–32199 = Filme pro Seite Dropdown) |
| `TmdbConfig.use_certification` | `lib/globals.py` | Noch nicht angelegt |
| TMDB Detail-API-Call | `lib/tmdb.py` | Noch nicht implementiert |
| FSK im Filter-Dialog | `lib/addon.py` | Noch nicht implementiert |
