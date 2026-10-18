# Versammlungsradar

Eine öffentliche, statische Website mit einem Zeitstrahl aller auffindbaren Versammlungen in Deutschland: zwölf Monate zurück und alle angemeldeten Termine voraus, filterbar nach Bundesland, Kreis und Stadt.

Architektur, Regeln und Bauphasen stehen in [ARCHITEKTUR.md](ARCHITEKTUR.md). Jeder Coding-Lauf liest diese Datei zuerst.

## Stand: Bauphase 1, Berlin

Eine Quelle ist angebunden: die Versammlungsliste der Polizei Berlin (Stufe 1, amtlich, § 8 VersFG BE).

- Der `ingest`-Workflow ruft sie dreimal täglich ab und übernimmt sie in die Monatsdateien.
- Die Zeit davor ist aus 81 Wayback-Snapshots nachgebaut, mit demselben Merge wie die Live-Abrufe.
- Stand 18.10.2026: 5.291 Ereignisse vom Oktober 2025 bis 2045 (jährliche Gedenktermine).

Bewusste Vereinfachungen bis Bauphase 3:

- Kategorie und Form setzen feste Stichwortregeln statt eines Modells.
- Orte liegen auf dem Mittelpunkt der Postleitzahl. Aufzüge ohne PLZ bekommen sie aus anderen Einträgen am selben Startpunkt.
- Vergangene Termine haben den Status `unklar`, bis die Presse-Schicht sie bestätigt.

## Datenmodell

Ein Ereignis ist eine Versammlung an einem Ort; wiederkehrende Termine mit gleichem Thema, Ort und Uhrzeit sind ein Ereignis mit mehreren `termine`. Das Schema steht in [schema/event.schema.json](schema/event.schema.json).

| Pfad | Inhalt |
| --- | --- |
| `data/events/JJJJ/MM.json` | Alle Ereignisse mit mindestens einem Termin im Monat, ein Ereignis pro Zeile. Ereignisse über Monatsgrenzen stehen in jedem betroffenen Monat mit derselben `id`. |
| `data/events/index.json` | Monate und Anzahl |
| `data/abrufe/<quelle>.json` | Jeder Abruf mit Zeit, Art (`aktuell` oder `archiv`), Zeilenzahl und Beleg-URL |
| `data/health.json` | Letzter Versuch, letzter Erfolg und Fehler je Quelle |

Regeln beim Merge (`radar/store.py`):

- Die `id` wird beim ersten Sehen vergeben und bleibt danach gleich. Der `schluessel` erkennt dasselbe Ereignis in späteren Abrufen.
- Vergangene Termine bleiben erhalten, auch wenn die Liste sie nicht mehr zeigt.
- Künftige Termine, die aus der Liste verschwinden, landen in `entfernte_termine`. Das ist kein Beleg für eine Absage.
- Enthält ein Abruf weniger als die Hälfte der bekannten künftigen Termine, wird er abgelehnt und der alte Stand bleibt.
- Vor dem Schreiben wird jedes Ereignis gegen das Schema geprüft. Bei einem Fehler wird nichts geschrieben.

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `radar/sources/berlin.py` | Adapter: Parser für die Berliner Liste |
| `radar/normalize.py` | Titel und Turnus, Kategorie, Form, Zeiten mit Zeitzone, Ortsschlüssel |
| `radar/geo.py` | PLZ-Mittelpunkt und Berliner Bezirk |
| `radar/store.py` | Merge, Status, Monatsdateien, Schema-Prüfung |
| `radar/rawstore.py` | Rohabrufe gzip-komprimiert ins private Repo, nur bei geändertem Inhalt |
| `radar/http.py` | Abruf mit Bot-Kennung, robots.txt-Prüfung, 1 Sekunde Abstand pro Host |
| `radar/site.py` | Statische Seite aus dem Store |
| `prototype/template.html` | Seite: Zeitstrahl, Karte, Filter, Detailkarte, Methodik |
| `tests/` | pytest gegen den gespeicherten Abruf vom 17.10.2026 |
| `sources.yaml` | Quellenregister |

## Lokal

```bash
uv venv && uv pip install -e ".[dev]"
scripts/fetch_geo.sh
.venv/bin/python -m pytest
.venv/bin/python -m radar ingest --source berlin --raw-repo ../versammlungsradar-raw
.venv/bin/python -m radar site
```

Weitere Befehle: `radar ingest --file <html> --fetched-at <ISO>` übernimmt einen gespeicherten Abruf, `radar backfill --snapshots <ordner>` übernimmt Wayback-Snapshots (`scripts/fetch_wayback.py` lädt sie), `radar validate` prüft alle Ereignisse gegen das Schema.

## Betrieb

| Workflow | Zeitplan | Aufgabe |
| --- | --- | --- |
| `ingest` | 05, 11, 17 Uhr UTC (07, 13, 19 Uhr Sommerzeit) | Abruf, Merge, Seite bauen, Commit von `data/` und `site/`, Rohabruf ins private Repo |
| `tests` | bei Push auf Branches und bei Pull Requests | pytest und Schema-Prüfung |

Der `ingest`-Workflow braucht das Repository-Secret `RAW_REPO_SSH_KEY`: der private Teil eines Deploy Keys mit Schreibrecht, der nur im Repo `versammlungsradar-raw` hinterlegt ist (Settings → Deploy keys). Schlägt ein Abruf fehl, bleibt der alte Stand online, `data/health.json` hält den Fehler fest und der Lauf wird rot.

## Lizenzen

- Code: [MIT](LICENSE)
- Ereignisdaten: [CC BY 4.0](data/LICENSE.md), Namensnennung „Versammlungsradar“
- Grundlage der Daten: Polizei Berlin, Versammlungsbehörde; Internet Archive (Wayback Machine). Der Test-Snapshot unter `tests/fixtures/` ist eine amtliche Bekanntmachung (§ 5 UrhG).
- Geodaten (nicht im Repo, beim Build geladen): PLZ-Mittelpunkte nach [WZB plz_geocoord](https://github.com/WZBSocialScienceCenter/plz_geocoord), Ländergrenzen nach [isellsoap/deutschlandGeoJSON](https://github.com/isellsoap/deutschlandGeoJSON), Bezirksgrenzen nach [funkeinteraktiv/Berlin-Geodaten](https://github.com/funkeinteraktiv/Berlin-Geodaten)

Angaben ohne Gewähr, maßgeblich ist die amtliche Quelle.
