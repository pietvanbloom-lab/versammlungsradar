# Versammlungsradar

Eine öffentliche, statische Website mit einem Zeitstrahl aller auffindbaren Versammlungen in Deutschland: zwölf Monate zurück und alle angemeldeten Termine voraus, filterbar nach Bundesland, Kreis und Stadt.

Architektur, Regeln und Bauphasen stehen in [ARCHITEKTUR.md](ARCHITEKTUR.md). Jeder Coding-Lauf liest diese Datei zuerst.

## Stand: Prototyp (Bauphase 1, Berlin)

Der Prototyp nutzt eine Quelle: die Versammlungsliste der Polizei Berlin (Stufe 1, amtlich).

- **Kommende Termine:** Abruf der aktuellen Liste vom 17.10.2026, 1.139 Zeilen.
- **Rückblick:** 81 Wayback-Snapshots derselben Liste vom 17.10.2025 bis 16.10.2026. Für jeden Tag gilt der jüngste Snapshot davor.
- **Ergebnis:** 3.563 Ereignisse. Wiederkehrende Termine mit gleichem Thema, Ort und Uhrzeit bilden ein Ereignis mit mehreren Tagen.

Bewusste Vereinfachungen gegenüber der Architektur:

- Kategorie und Form setzen feste Stichwortregeln statt eines Modells.
- Orte liegen auf dem Mittelpunkt der Postleitzahl. Bei Aufzügen ohne PLZ wird sie aus anderen Einträgen am selben Startpunkt abgeleitet.
- Vergangene Termine haben den Status „unklar“ (ohne Nachlauf), bis die Presse-Schicht sie bestätigt.
- Die Ereignisdaten liegen als eine kompakte Datei vor, noch nicht als Monatsdateien nach `data/events/JJJJ/MM.json`.

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `ARCHITEKTUR.md` | Ziel, Quellen, Datenmodell, Pipeline, Betrieb, Recht, Bauphasen |
| `sources.yaml` | Quellenregister |
| `pipeline/fetch_current.sh` | Aktuelle Berliner Liste abrufen |
| `pipeline/fetch_wayback.py` | Wayback-Snapshots für den Rückblick laden |
| `pipeline/fetch_geo.sh` | PLZ-Mittelpunkte, Länder- und Bezirksgrenzen laden |
| `pipeline/build.py` | Parser, Normalisierung, Gruppierung, Kategorien → `data/prototyp/berlin.json` |
| `pipeline/assemble.py` | Template und Daten → `site/versammlungsradar.html` |
| `prototype/template.html` | Seite: Zeitstrahl, Karte, Filter, Detailkarte, Methodik |
| `data/` | Extrahierte Ereignisdaten (CC BY 4.0) |
| `site/` | Gebaute statische Seite |

Rohabrufe landen in `raw/` und sind per `.gitignore` ausgeschlossen. Sie gehören laut Architektur in das private Repo `versammlungsradar-raw`.

## Lokal bauen

```bash
pipeline/fetch_geo.sh
pipeline/fetch_current.sh
python3 pipeline/fetch_wayback.py raw/wayback
python3 pipeline/build.py
python3 pipeline/assemble.py
```

Danach `site/versammlungsradar.html` im Browser öffnen. Das Stichdatum (`TODAY`) steht noch fest in `pipeline/build.py`.

## Lizenzen

- Code: [MIT](LICENSE)
- Ereignisdaten: [CC BY 4.0](data/LICENSE.md), Namensnennung „Versammlungsradar“
- Grundlage der Daten: Polizei Berlin, Versammlungsbehörde; Internet Archive (Wayback Machine)
- Geodaten (nicht im Repo, beim Build geladen): PLZ-Mittelpunkte nach [WZB plz_geocoord](https://github.com/WZBSocialScienceCenter/plz_geocoord), Ländergrenzen nach [isellsoap/deutschlandGeoJSON](https://github.com/isellsoap/deutschlandGeoJSON), Bezirksgrenzen nach [funkeinteraktiv/Berlin-Geodaten](https://github.com/funkeinteraktiv/Berlin-Geodaten)

Angaben ohne Gewähr, maßgeblich ist die amtliche Quelle.
