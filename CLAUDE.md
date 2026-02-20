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

### Übersicht: 4 Einstellungen im Abschnitt [Cache]

| Setting-ID | Typ | Standard | Bedeutung |
|---|---|---|---|
| `cache_enabled` | boolean | `true` | Lokalen Stalker-Cache verwenden (ja/nein) |
| `load_all_pages` | boolean | `false` | Alle Seiten auf einmal laden statt paginiert |
| `refresh_all_data` | boolean | `false` | Alles löschen + komplett neu laden |
| `update_new_data` | boolean | `false` | Nur neue Inhalte zum Cache hinzufügen |

---

### Verhaltensmatrix: `cache_enabled` × `load_all_pages`

| `cache_enabled` | `load_all_pages` | Ergebnis beim Ordner öffnen |
|---|---|---|
| AUS | AUS | Seitenweise vom Server (~20 Filme, Weiter/Zurück-Schaltflächen) |
| AUS | EIN | Alle Seiten vom Server auf einmal (langsam beim ersten Mal) |
| **EIN** | AUS | Seitenweise vom Server – kein Cache-Nutzen für normale Ansicht |
| **EIN** | EIN | Alle Filme sofort aus lokalem Cache ✓ (falls Cache leer → alle Seiten vom Server) |

> **Empfehlung:** Beide EIN = schnellste Nutzererfahrung nach dem ersten Refresh.

**Wo gesetzt:** `globals.py::init_globals()` → `self.addon_config.max_page_limit` und `self.addon_config.cache_enabled`

**Codelogik in `__list_vod` / `__list_series`:**
```python
load_all = G.addon_config.max_page_limit >= 9999   # load_all_pages=true
use_cache = G.addon_config.cache_enabled
if load_all and use_cache and not search_term.strip() and fav == '0':
    cached = StalkerCache(...).get_videos(...)
    if cached:
        videos = {'data': cached, ...}   # sofort aus Cache
if videos is None:
    videos = Api.get_videos(...)         # Fallback: Server
```

---

### "Alle Daten aktualisieren" (`refresh_all_data`)

**Kein** `type="action"` – das funktioniert in Kodi 21 nicht (→ Regel 1 oben).
Stattdessen `type="boolean"` Toggle. Service erkennt `value == 'true'` in
`onSettingsChanged()`, setzt sofort zurück auf `false`, ruft `RunPlugin(...?action=refresh_all)` auf.

**Implementiert in:** `addon.py::__refresh_all_data()` + `lib/service.py::onSettingsChanged()`

**Ablauf:**
1. Öffnet `xbmcgui.DialogProgress()` mit Abbrechen-Schaltfläche
2. Lädt alle VOD- + alle Series-Kategorien vom Server → speichert in Stalker-Cache
3. Iteriert über jede Kategorie, lädt **alle** Videos (`max_page_limit=9999` temporär)
4. Speichert Videolisten in lokalem Stalker-Cache (JSON pro Kategorie)
5. Falls TMDB aktiv: holt Metadaten pro Film → befüllt 30-Tage-TMDB-Cache
6. `tmdb.flush()` nach jeder Kategorie (1 Disk-Write statt N)
7. Fortschrittsbalken: `[X/Y] Kategoriename: Filmtitel`
8. Abbrechen jederzeit möglich

**Primärer Nutzen:** Kompletten Cache aufbauen. Danach öffnet jede Kategorie sofort (<1s).
**Silent-Modus:** `?action=refresh_all&silent=1` → kein Dialog (für Hintergrundnutzung durch Service).

---

### "Nur neue Inhalte hinzufügen" (`update_new_data`)

Gleicher Toggle-Workaround wie `refresh_all_data`. Service → `RunPlugin(...?action=update_new_data)`.

**Implementiert in:** `addon.py::__update_new_data()` + `lib/service.py::onSettingsChanged()`

**Ablauf:**
1. Öffnet `xbmcgui.DialogProgress()` mit Abbrechen-Schaltfläche
2. Lädt alle Kategorien (gefiltert)
3. Für jede Kategorie: Serverliste holen → mit Cache vergleichen (nach `id`)
4. **Nur neue Filme** → werden dem Cache vorangestellt (erscheinen oben)
5. Falls TMDB aktiv: TMDB-Lookup nur für die neuen Filme → `tmdb.flush()`
6. Vorhandene Filme + TMDB-Daten bleiben **unverändert**
7. Zeigt am Ende: „X neue Inhalte hinzugefügt."

**Wann benutzen:**
- Regelmäßig (z.B. wöchentlich) um neue Veröffentlichungen einzuspielen
- Deutlich schneller als `refresh_all_data` wenn der Katalog sich kaum ändert

**Wenn TMDB nicht konfiguriert:** TMDB-Schritt wird einfach übersprungen – kein Fehler.

---

### Täglicher Hintergrund-Refresh (Service)

Der `BackgroundService.run()` prüft beim Kodi-Start ob der Stalker-Cache älter als 24h ist.
Falls ja → startet `refresh_all` im Silent-Modus lautlos im Hintergrund.

**Respektiert `cache_enabled`:** Wenn der Nutzer den Cache deaktiviert hat, wird der
tägliche Refresh nicht ausgelöst.

**Prüfung:** `StalkerCache.categories_are_stale('vod')` → vergleicht Datei-Timestamp.

---

### Lokaler Stalker-Cache (`lib/stalker_cache.py`)

| Inhalt | Datei | Gültigkeit |
|---|---|---|
| VOD-Kategorien | `stalker_categories_vod.json` | 24h |
| Series-Kategorien | `stalker_categories_series.json` | 24h |
| VOD-Videos (pro Kategorie) | `stalker_videos_vod_{id}.json` | 24h |
| Series-Videos (pro Kategorie) | `stalker_videos_series_{id}.json` | 24h |

Alle Dateien liegen in `{kodi_profile}/plugin.video.stalkervod.tmdb/`.

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

## Ersteinrichtungs-Dialog (wie Stalker PVR)

### Ablauf
1. Nutzer öffnet Einstellungen und gibt Serveradresse + MAC-Adresse ein
2. Kodi ruft `BackgroundService.onSettingsChanged()` auf (bei jeder Einstellungsänderung)
3. Wenn **beide Felder** gesetzt sind und die Flag-Datei `initial_setup_done` **nicht** existiert:
   - Flag-Datei wird sofort erstellt (verhindert mehrfaches Anzeigen)
   - Ja/Nein-Dialog: "Sollen alle VOD-Daten jetzt geladen werden?"
   - Bei "Ja": `RunPlugin(...?action=refresh_all)` → startet Bulk-Download mit Fortschrittsbalken
4. Bei "Nein" oder Abbruch: Button "Alle Daten aktualisieren" in den Einstellungen steht weiterhin bereit

### Flag-Datei
- Pfad: `{kodi_profile}/plugin.video.stalkervod.tmdb/initial_setup_done` (leere Datei)
- Existiert diese Datei → Dialog erscheint nie wieder automatisch
- Manuelle Alternative: Button "Alle Daten aktualisieren" in den Portal-Einstellungen

### Warum onSettingsChanged und nicht onStart?
`onSettingsChanged` im Service wird von Kodi aufgerufen sobald der Nutzer eine Einstellung
ändert und bestätigt. Das ist der nächstmögliche Zeitpunkt nach der Eingabe der Anmeldedaten –
exakt das Verhalten, das Stalker PVR beim ersten Start zeigt.

**Hinweis für zukünftige Sessions:** Wenn der Nutzer den Server wechselt und eine neue
Ersteinrichtung triggern möchte, muss die Flag-Datei gelöscht werden.
Dafür könnte ein Reset-Button in den Einstellungen ergänzt werden (noch nicht umgesetzt).

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

Die `settings.xml` hat **vier `<section>`-Blöcke** mit der gleichen `id="plugin.video.stalkervod.tmdb"` –
das ist in Kodi valide, die Sections sind visuelle Tabs/Kategorien.

### Portal-Tab
| Setting-ID | Typ | Bedeutung |
|---|---|---|
| `server_address` | string | Stalker-Server-URL |
| `alternative_context_path` | boolean | `/portal.php` statt `/server/load.php` |
| `mac_address` | string | MAC-Adresse des Geräts |
| `serial_number` | string | Seriennummer |
| `device_id` | string | Geräte-ID 1 |
| `device_id_2` | string | Geräte-ID 2 |
| `signature` | string | Signatur |

### Ordner-Filter-Tab
| Setting-ID | Typ | Bedeutung |
|---|---|---|
| `folder_filter_use_keywords` | boolean | Stichwörter-Filter aktiv |
| `folder_filter_use_manual` | boolean | Manuelle Auswahl aktiv (hat Vorrang) |
| `folder_filter_keywords` | string | Kommagetrennte Stichwörter |
| `folder_filter_select_vod` | boolean | Toggle → öffnet VOD-Auswahldialog |
| `folder_filter_select_series` | boolean | Toggle → öffnet Serien-Auswahldialog |
| `folder_filter_select_tv` | boolean | Toggle → öffnet TV-Auswahldialog |

### Cache-Tab ← NEU
| Setting-ID | Typ | Standard | Bedeutung |
|---|---|---|---|
| `cache_enabled` | boolean | `true` | Lokalen Cache verwenden (aus = immer Server) |
| `load_all_pages` | boolean | `false` | Alle Seiten auf einmal statt paginiert |
| `refresh_all_data` | **boolean** (kein action!) | `false` | Alles löschen + komplett neu laden |
| `update_new_data` | **boolean** (kein action!) | `false` | Nur neue Inhalte zum Cache hinzufügen |

### TMDB-Tab
| Setting-ID | Typ | Bedeutung |
|---|---|---|
| `tmdb_enabled` | boolean | TMDB-Anreicherung ein/aus |
| `tmdb_api_key` | string (hidden) | Kostenloser Key von themoviedb.org |
| `tmdb_language` | string | Sprach-Code für Metadaten, default `de-DE` |

> **Wichtig:** Alle Schalter die wie Buttons wirken (`refresh_all_data`, `update_new_data`,
> `folder_filter_select_*`) sind bewusst `type="boolean"`. Hintergrund: `type="action"` mit
> `<action>`-Child funktioniert in Kodi 21 nicht (→ Regel 1 oben).
> Der Service setzt jeden Schalter sofort zurück auf `false` nachdem er die Aktion gestartet hat.

---

## Für den nächsten Merge / nächste Session

- Branch: `claude/review-addon-settings-docs-uVHz3`
- Alle Commits sind gepusht
- ZIP für direkten Download: `dist/plugin.video.stalkervod.tmdb-0.2.4.zip`
- ZIP-Erstellung ist jetzt Pflicht am Sitzungsende (siehe Abschnitt oben)
- **Nach ZIP-Erstellung immer auch CLAUDE.md aktualisieren** (diese Datei!)

### Zuletzt umgesetzte Features

| Feature | Branch | Beschreibung |
|---|---|---|
| Spickzettel KODI_SETTINGS_REFERENCE.md | `claude/review-addon-settings-docs-uVHz3` | Neue Datei mit verifizierten Syntax-Beispielen für alle settings.xml Control-Typen in Kodi 21. CLAUDE.md verweist darauf. Alte Syntax-Blöcke aus CLAUDE.md entfernt. |
| Sprach-Dropdown statt Freitextfeld | `claude/review-addon-settings-docs-uVHz3` | `tmdb_language` ist jetzt ein Spinner mit 9 Sprachen (de-DE, en-US, en-GB, fr-FR, it-IT, es-ES, nl-NL, pl-PL, tr-TR). Neue String-IDs 32160–32168 in beiden .po-Dateien. |
| `<dependencies>` Syntax überall | `claude/review-addon-settings-docs-uVHz3` | Alle alten `<enable>eq(...)` und `<enable>eq(-1,true)</enable>` Syntax durch korrekte `<dependencies><dependency type="enable">` Blöcke ersetzt. Alle TMDB-Settings werden beim Deaktivieren korrekt ausgegraut. |
| `<close>true</close>` bei Refresh-Buttons | `claude/review-addon-settings-docs-uVHz3` | "Alle Daten aktualisieren", "Nur neue Inhalte", "TMDB-Metadaten aktualisieren" schließen Einstellungen automatisch bevor der Fortschrittsbalken erscheint. |
| Ja/Nein-Dialog bei Cache löschen | `claude/review-addon-settings-docs-uVHz3` | Vor dem Löschen des TMDB-Caches erscheint eine Bestätigungsabfrage. Verhindert versehentliches Löschen. |
| API-Key sichtbar (kein Sternchen) | `claude/review-addon-settings-docs-uVHz3` | `hidden="true"` vom API-Key-Feld entfernt. Der Schlüssel ist jetzt im Klartext sichtbar (kein Verstecken nötig). |
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
| `fanart`/`votes` weglassen (optional per Setting) | mittel | weniger Kodi-Bandbreite |
| Timeout für TMDB-Calls kürzen (aktuell 10s → 3s) | klein | hängt nicht 10s bei Offline-TMDB |
| FSK-Altersfreigaben (zweiter API-Call pro Film nötig) | mittel | verdoppelt Ladezeit bei leerem Cache |
| Parallele TMDB-Requests beim Refresh (Threading) | groß | Refresh deutlich schneller (statt sequenziell) |
