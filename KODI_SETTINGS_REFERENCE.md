# Kodi Settings XML – Spickzettel

> **PFLICHT: Diese Datei VOR dem Coden lesen!**
> Alle Beispiele sind gegen Kodi 21 (Omega) mit `settings version="1"` getestet
> und aus echten Addons (TMDb Helper, pvr.dvbviewer) verifiziert.

---

## Grundstruktur

```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<settings version="1">
    <section id="plugin.video.stalkervod.tmdb">
        <category id="mein_tab" label="32001">
            <group id="meine_gruppe" label="32002">
                <!-- Settings hier -->
            </group>
        </category>
    </section>
</settings>
```

---

## 1. Boolean Toggle (Ein/Aus-Schalter)

```xml
<setting id="mein_toggle" type="boolean" label="32010" help="32011">
    <level>0</level>
    <default>false</default>
    <control type="toggle" />
</setting>
```

---

## 2. Action Button (echter Klick-Button)

```xml
<setting id="mein_button" type="action" label="32020" help="32021">
    <level>0</level>
    <close>true</close>   <!-- Schließt Einstellungen vor Ausführung (optional) -->
    <data>RunPlugin(plugin://plugin.video.stalkervod.tmdb/?action=meine_aktion)</data>
    <constraints>
        <allowempty>true</allowempty>
    </constraints>
    <control type="button" format="action" />
</setting>
```

**Wichtig:**
- `<data>` statt `<action>` – das ist die korrekte Version-1-Syntax
- `format="action"` am `<control>` ist **Pflicht** (sonst unsichtbar)
- `&` in URLs → `&amp;`: `?action=foo&amp;type=bar`
- `<close>true</close>` → Einstellungen schließen sich vor dem RunPlugin (sinnvoll bei Fortschrittsbalken)
- `getSetting('mein_button')` gibt immer `''` zurück (kein gespeicherter Wert)

❌ **ALTES Format – NICHT benutzen:**
```xml
<setting id="mein_button" type="action" label="32020">
    <action>RunPlugin(...)</action>   <!-- falsch: <action> statt <data> -->
    <control type="button" />         <!-- falsch: fehlendes format="action" -->
</setting>
```

---

## 3. String Dropdown/Spinner (Auswahl aus Text-Werten)

Der gespeicherte Wert ist der Text innerhalb von `<option>...</option>`.
Der `label`-Wert ist nur die Anzeigebezeichnung (String-ID).

```xml
<setting id="meine_sprache" type="string" label="32030" help="32031">
    <level>0</level>
    <default>de-DE</default>
    <constraints>
        <options>
            <option label="32032">de-DE</option>    <!-- gespeichert: "de-DE" -->
            <option label="32033">en-US</option>    <!-- gespeichert: "en-US" -->
            <option label="32034">fr-FR</option>    <!-- gespeichert: "fr-FR" -->
        </options>
    </constraints>
    <control type="spinner" format="string" />
</setting>
```

Python-Zugriff:
```python
sprache = addon.getSetting('meine_sprache')   # z.B. "de-DE"
```

---

## 4. Integer Dropdown/Spinner (Auswahl aus benannten Optionen)

Der gespeicherte Wert ist der Zahlenindex (0, 1, 2, ...) – **nicht** der Label-Text.

```xml
<setting id="mein_modus" type="integer" label="32040" help="32041">
    <level>0</level>
    <default>0</default>
    <constraints>
        <options>
            <option label="32042">0</option>   <!-- gespeichert: 0 → "Alles anzeigen" -->
            <option label="32043">1</option>   <!-- gespeichert: 1 → "Nur Deutsch" -->
            <option label="32044">2</option>   <!-- gespeichert: 2 → "Nur Favoriten" -->
        </options>
    </constraints>
    <control type="spinner" format="integer" />
</setting>
```

❌ **FALSCH – `subtype=` gibt es nicht:**
```xml
<control type="spinner" subtype="integer" />   <!-- falsch: subtype= → kodi wirft setting weg -->
```
✅ **KORREKT:** `format="integer"` – immer `format=` nicht `subtype=`

Python-Zugriff:
```python
modus = int(addon.getSetting('mein_modus') or '0')
if modus == 1:
    pass  # Nur Deutsch
```

---

## 5. Integer Bereich (Zahlenrad mit min/max/step)

Wenn der Nutzer eine Zahl in einem Bereich wählen soll (z.B. Tage 1–365):

```xml
<setting id="cache_tage" type="integer" label="32050" help="32051">
    <level>0</level>
    <default>30</default>
    <constraints>
        <minimum>1</minimum>
        <maximum>365</maximum>
        <step>1</step>
    </constraints>
    <control type="spinner" format="integer" />
</setting>
```

Python-Zugriff:
```python
tage = int(addon.getSetting('cache_tage') or '30')
```

---

## 6. Text-Eingabefeld (String Edit)

```xml
<setting id="mein_text" type="string" label="32060" help="32061">
    <level>0</level>
    <default>Standardwert</default>
    <constraints>
        <allowempty>true</allowempty>
    </constraints>
    <control type="edit" format="string" />
</setting>
```

---

## 7. Abhängigkeiten: Ausgrauen / Verbergen

### 7a. Ausgrauen wenn anderes Setting aus ist (`type="enable"`)

```xml
<setting id="abhaengiges_setting" type="string" label="32070">
    <level>0</level>
    <dependencies>
        <dependency type="enable">
            <condition operator="is" setting="mein_toggle">true</condition>
        </dependency>
    </dependencies>
    <control type="edit" format="string" />
</setting>
```

### 7b. Verbergen wenn Textfeld leer ist (`type="visible"`)

```xml
<setting id="nur_sichtbar_wenn_key_gesetzt" type="boolean" label="32071">
    <level>0</level>
    <dependencies>
        <dependency type="visible">
            <condition operator="!" setting="api_key"></condition>
        </dependency>
    </dependencies>
    <control type="toggle" />
</setting>
```

### 7c. Mehrere Bedingungen (UND-Verknüpfung)

```xml
<setting id="doppelt_abhaengig" type="boolean" label="32072">
    <level>0</level>
    <dependencies>
        <dependency type="enable">
            <condition operator="is" setting="tmdb_enabled">true</condition>
        </dependency>
        <dependency type="enable">
            <condition operator="is" setting="cache_enabled">true</condition>
        </dependency>
    </dependencies>
    <control type="toggle" />
</setting>
```

**Wichtig:**
- `setting="..."` → Einstellungs-ID ohne Anführungszeichen um den Wert
- Für boolean: Wert ist `true` oder `false` (kleingeschrieben)
- `operator="is"` → exakter Vergleich
- `operator="!"` → Negierung (Setting ist leer / falsch)
- Settings aus **anderen Gruppen oder Sections** können trotzdem referenziert werden – einfach die ID nehmen

❌ **ALTE SYNTAX – nicht mehr benutzen:**
```xml
<enable>eq(-1,true)</enable>          <!-- veraltet: relativer Offset -->
<enable>eq(tmdb_enabled,true)</enable> <!-- veraltet: funktioniert teils noch, aber fragil -->
```

---

## 8. Separator (Trennlinie)

```xml
<setting type="sep" />                          <!-- unsichtbare Trennlinie -->
<setting type="lsep" label="32080" />           <!-- Abschnitts-Überschrift -->
```

---

## 9. Sprachdateien – IMMER BEIDE pflegen!

Bei **jeder** neuen String-ID **beide** Dateien aktualisieren:

| Datei | Zweck |
|---|---|
| `resources/language/resource.language.en_gb/strings.po` | Englisch – Fallback wenn keine Übersetzung |
| `resources/language/resource.language.de_de/strings.po` | Deutsch – primär für den Nutzer |

**Format in beiden Dateien:**
```
msgctxt "#32XXX"
msgid "Englischer Text"
msgstr "Deutscher Text"
```

Fehlt ein String in `de_de/strings.po` → Kodi zeigt nichts (leeres Element, kein Fehler).
Fehlt ein String in `en_gb/strings.po` → kein Fallback → Element unsichtbar.

**Nächste freie String-ID:** aktuell #32169 (IDs 32001–32168 sind vergeben)

---

## 10. Vollständiges Beispiel: TMDB-Tab-Gruppe

```xml
<group id="tmdb_general" label="32101">

    <!-- 1. Haupt-Toggle (keine Abhängigkeit) -->
    <setting id="tmdb_enabled" type="boolean" label="32102" help="32103">
        <level>0</level>
        <default>false</default>
        <control type="toggle" />
    </setting>

    <!-- 2. Text-Eingabe, ausgegraut wenn TMDB aus -->
    <setting id="tmdb_api_key" type="string" label="32104" help="32105">
        <level>0</level>
        <dependencies>
            <dependency type="enable">
                <condition operator="is" setting="tmdb_enabled">true</condition>
            </dependency>
        </dependencies>
        <constraints>
            <allowempty>true</allowempty>
        </constraints>
        <control type="edit" format="string" />
    </setting>

    <!-- 3. String-Dropdown, ausgegraut wenn TMDB aus -->
    <setting id="tmdb_language" type="string" label="32106" help="32107">
        <level>0</level>
        <dependencies>
            <dependency type="enable">
                <condition operator="is" setting="tmdb_enabled">true</condition>
            </dependency>
        </dependencies>
        <default>de-DE</default>
        <constraints>
            <options>
                <option label="32160">de-DE</option>
                <option label="32161">en-US</option>
                <option label="32162">en-GB</option>
            </options>
        </constraints>
        <control type="spinner" format="string" />
    </setting>

    <!-- 4. Action-Button, ausgegraut wenn TMDB aus, schließt Einstellungen -->
    <setting id="mein_refresh" type="action" label="32110" help="32111">
        <level>0</level>
        <dependencies>
            <dependency type="enable">
                <condition operator="is" setting="tmdb_enabled">true</condition>
            </dependency>
        </dependencies>
        <close>true</close>
        <data>RunPlugin(plugin://plugin.video.stalkervod.tmdb/?action=meine_aktion)</data>
        <constraints>
            <allowempty>true</allowempty>
        </constraints>
        <control type="button" format="action" />
    </setting>

</group>
```

---

## 11. Häufige Fehler-Checkliste

| Symptom | Ursache | Fix |
|---|---|---|
| Button unsichtbar | `<action>` statt `<data>`, oder fehlendes `format="action"` | Syntax aus Abschnitt 2 verwenden |
| Spinner/Dropdown unsichtbar | `subtype=` statt `format=` | `<control type="spinner" format="integer" />` |
| Setting wird beim Neustart ignoriert | Relative `eq(-1,true)` Abhängigkeit nach Umbau | `<dependencies>` Syntax aus Abschnitt 7 nutzen |
| Ausgrauen funktioniert nicht | Alte `<enable>eq(...)` Syntax | Zu `<dependencies>` migrieren |
| Deutsches Setting leer | String-ID fehlt in `de_de/strings.po` | Beide .po-Dateien pflegen |
| Kodi ignoriert Setting komplett | Fehlende String-ID in `en_gb/strings.po` | Beide .po-Dateien pflegen |
