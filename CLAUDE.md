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

## ⚠️ KODI 21 (OMEGA) – BEKANNTE EINSCHRÄNKUNGEN & PFLICHT-WISSEN

> **Diese Regeln MÜSSEN in jeder Session beachtet werden, sonst entstehen unsichtbare UI-Elemente.**

### REGEL 1: Kein `type="action"` mit `<action>`-Child in `settings version="1"`

**Problem:** In Kodi 21 (Omega) mit `<settings version="1">` ist das `<action>`-Tag
als Child von `<setting type="action">` **nicht valide**. Kodi 21 ignoriert es still –
und wirft dabei die **gesamte `<group>`** weg. Der Nutzer sieht gar nichts.

```xml
<!-- ❌ FUNKTIONIERT NICHT in Kodi 21 settings version="1" -->
<setting id="my_button" type="action" label="32001">
    <action>RunPlugin(plugin://...)</action>   <!-- ← dieser Tag killt die ganze Gruppe -->
    <control type="button" />
</setting>
```

**Workaround – IMMER SO MACHEN:**
```xml
<!-- ✅ KORREKT: boolean toggle als Auslöser -->
<setting id="my_button" type="boolean" label="32001" help="32002">
    <level>0</level>
    <default>false</default>
    <control type="toggle" />
</setting>
```

Dazu im Service (`lib/service.py`) in `onSettingsChanged()`:
```python
addon = xbmcaddon.Addon()
if addon.getSetting('my_button') == 'true':
    addon.setSetting('my_button', 'false')   # sofort zurücksetzen
    xbmc.executebuiltin('RunPlugin(plugin://...?action=do_something)')
    return
```

**Warum funktioniert das?**
- `type="boolean"` ist vollständig valide in allen Kodi-Versionen.
- Kodi ruft `onSettingsChanged()` im Service auf, sobald der Nutzer den Schalter umlegt.
- Der Service setzt den Wert sofort zurück auf `false` (der Schalter springt zurück).
- Anschließend startet er `RunPlugin(...)` → der gewünschte Effekt tritt ein.

### REGEL 2: Sprachdateien – immer BEIDE Dateien pflegen

Wenn neue String-IDs hinzugefügt werden, **immer in beiden Dateien** eintragen:
- `resources/language/resource.language.en_gb/strings.po` (Englisch – Fallback)
- `resources/language/resource.language.de_de/strings.po` (Deutsch – primär für den Nutzer)

Kodi lädt automatisch die passende Sprachdatei. Fehlt ein String, wird das `<group>`-
oder `<setting>`-Element möglicherweise ausgeblendet (kein Fehler, nur leer/unsichtbar).

### REGEL 3: `onSettingsChanged` wird bei JEDER Einstellungsänderung aufgerufen

Nicht nur bei der Ersteinrichtung oder beim Refresh-Button. Jede Änderung einer beliebigen
Einstellung feuert diesen Callback. Deshalb ist die **genaue Reihenfolge der Prüfungen** wichtig:

```python
def onSettingsChanged(self):
    addon = xbmcaddon.Addon()
    # 1. Zuerst: Refresh-Button prüfen (spezifisch, kein Server nötig)
    if addon.getSetting('refresh_all_data') == 'true':
        addon.setSetting('refresh_all_data', 'false')
        xbmc.executebuiltin('RunPlugin(...?action=refresh_all)')
        return   # ← return verhindert, dass der Ersteinrichtungs-Check ebenfalls läuft
    # 2. Dann: Ersteinrichtungs-Check (nur wenn Server + MAC gesetzt und Flag nicht da)
    ...
```

### REGEL 4: Kein `type="integer"` mit Spinner und `<options>` in `settings version="1"`

**Problem:** In Kodi 21 (Omega) schlägt `type="integer"` mit
`<control type="spinner" subtype="integer" />` und `<options>`-Block fehl,
weil Kodi ein `format`-Attribut am Control erwartet – das bei Spinner-Controls
nicht vorgesehen ist. Fehler im Log:

```
error <ISettingControl>: error reading "format" attribute of <control>
error <CSetting>: error reading <control> tag of "my_setting"
warning <CSettingGroup>: unable to read setting "my_setting"
```

Das Setting wird **lautlos weggeworfen**. In der UI fehlt nur dieses eine Element –
aber da der gespeicherte Wert nie geladen wird, bleibt die Variable intern auf ihrem
Standardwert (z.B. 0 = aus). Alle anderen Settings in der Gruppe bleiben sichtbar,
wirken aber nicht, weil der Modus-Wert fehlt.

```xml
<!-- ❌ FUNKTIONIERT NICHT in Kodi 21 settings version="1" -->
<setting id="my_mode" type="integer" label="32001">
    <constraints>
        <options>
            <option label="32002">0</option>
            <option label="32003">1</option>
        </options>
    </constraints>
    <control type="spinner" subtype="integer" />   <!-- ← fehlendes format= killt das Setting -->
</setting>
```

**Workaround – IMMER SO MACHEN:**
Für Mehrfach-Auswahl (z.B. 3 Modi) statt eines Spinners **mehrere `type="boolean"` Toggles** verwenden:

```xml
<!-- ✅ KORREKT: zwei boolean toggles statt eines 3-Wege-Spinners -->
<setting id="filter_use_keywords" type="boolean" label="32001" help="32002">
    <level>0</level>
    <default>false</default>
    <control type="toggle" />
</setting>
<setting id="filter_use_manual" type="boolean" label="32003" help="32004">
    <level>0</level>
    <default>false</default>
    <control type="toggle" />
</setting>
```

Im Python-Code dann einfach:
```python
if cfg.use_manual:
    # manuelle Auswahl (hat Vorrang)
elif cfg.use_keywords:
    # Stichwörter-Filter
# sonst: alles anzeigen
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
| `lib/tmdb.py` | TMDB API Client + 30-Tage-Cache |
| `lib/addon.py` | Kodi ListItem-Aufbau, TMDB-Felder anwenden |
| `lib/api.py` | Stalker Middleware API Client |
| `lib/auth.py` | Stalker Authentifizierung / Token-Verwaltung |
| `resources/settings.xml` | Kodi Einstellungen (zwei Sections, gleiche Addon-ID) |
| `resources/language/resource.language.en_gb/strings.po` | String-IDs (32100–32114) – immer parallel in `de_de/strings.po` pflegen! |
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

## Laden-Strategie & Bulk-Refresh

### "Alle Seiten laden" (`load_all_pages`)

Standardmäßig lädt das Addon `max_page_limit = 2` Server-Seiten pro Kodi-Listing-Seite.
Mit `load_all_pages = true` wird `max_page_limit = 9999` gesetzt → alle Seiten werden auf einmal abgerufen.

**Wann sinnvoll:**
- TMDB deaktiviert: kein Metadaten-Overhead, nur Stalker-Daten → gesamte Kategorie in 1–3s
- TMDB aktiviert: nicht empfohlen (erste Nutzung: jeder Film ~300ms → bei 200 Filmen ~60s)

**Wo gesetzt:** `globals.py::init_globals()` → `self.addon_config.max_page_limit`

### "Daten aktualisieren" Schalter (`refresh_all_data`)

**Kein** `type="action"` – das funktioniert in Kodi 21 nicht (→ Regel 1 oben).
Stattdessen: `type="boolean"` Toggle. Der Service erkennt `value == 'true'` in
`onSettingsChanged()`, setzt den Schalter sofort zurück auf `false` und ruft
`RunPlugin(...?action=refresh_all)` auf.
Implementiert in `addon.py::__refresh_all_data()` + `lib/service.py::onSettingsChanged()`.

**Ablauf:**
1. Öffnet `xbmcgui.DialogProgress()` mit Abbrechen-Schaltfläche
2. Lädt alle VOD-Kategorien + alle Series-Kategorien (je ein API-Call)
3. Iteriert über jede Kategorie, lädt alle Videos (`max_page_limit=9999` temporär)
4. Falls TMDB aktiv: ruft `tmdb.get_movie_info()` / `tmdb.get_tv_info()` pro Film auf → befüllt 30-Tage-Cache
5. `tmdb.flush()` nach jeder Kategorie (1 Disk-Write pro Kategorie statt pro Film)
6. Fortschrittsbalken zeigt `[Kategorie X/Y] Kategoriename: Filmname`
7. Abbrechen jederzeit möglich (zwischen Filmen geprüft)

**Primärer Nutzen:** TMDB-Cache vorwärmen. Nach einmaligem Durchlauf lädt jede Kategorie sofort.
**Ohne TMDB:** Läuft durch, macht aber ohne Cache-Ziel wenig (Stalker-Daten werden nicht gecacht).

**Routing:** `router()` → `elif params['action'] == 'refresh_all': self.__refresh_all_data()`
**Kein `endOfDirectory`-Call** – RunPlugin-Aktionen benötigen das nicht.

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
| `load_all_pages` | boolean | Alle Server-Seiten auf einmal laden (max_page_limit=9999), Standard: false (=2 Seiten) |
| `refresh_all_data` | **boolean** (kein action!) | Schalter-Workaround: einschalten → Service startet Refresh + setzt Schalter zurück |

> **Wichtig:** `refresh_all_data` ist bewusst `type="boolean"`, obwohl es sich wie ein Button verhält.
> Hintergrund: `type="action"` mit `<action>`-Child funktioniert in Kodi 21 nicht (→ Regel 1 oben).

Die `settings.xml` hat **zwei `<section>`-Blöcke** mit der gleichen `id="plugin.video.stalkervod.tmdb"` –
das ist in Kodi valide, die Sections sind visuelle Gruppierungen.

---

## Für den nächsten Merge / nächste Session

- Branch: `claude/optimize-data-refresh-S8crk`
- Alle Commits sind gepusht
- ZIP für direkten Download: `dist/plugin.video.stalkervod.tmdb-0.1.3.zip`
- ZIP-Erstellung ist jetzt Pflicht am Sitzungsende (siehe Abschnitt oben)
- **Nach ZIP-Erstellung immer auch CLAUDE.md aktualisieren** (diese Datei!)

### Zuletzt umgesetzte Features

| Feature | Branch | Beschreibung |
|---|---|---|
| load_all_pages Cache-Fix | `claude/optimize-data-refresh-S8crk` | `load_all_pages=true` überspringt jetzt den Cache und holt immer frisch vom Server (alle Seiten). `load_all_pages=false` (Standard) nutzt den Cache. |
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
