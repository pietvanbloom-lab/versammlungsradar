"""Ereignisspeicher: Monatsdateien unter data/events/JJJJ/MM.json, Merge neuer Abrufe, Status.

Ein Ereignis steht in jeder Monatsdatei, in die einer seiner Termine fällt, jedes Mal vollständig und
mit derselben id. Wer mehrere Monate lädt, entfernt Dubletten über die id.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator

from . import normalize as N
from .geo import Geo
from .normalize import TZ

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "event.schema.json").read_text(encoding="utf-8"))
_validator = Draft202012Validator(SCHEMA)

# Ein Abruf mit weniger als diesem Anteil der bekannten künftigen Termine gilt als verdächtig
# (abgeschnittene Liste, Umbau der Seite) und wird nicht übernommen.
MIN_SHARE = 0.5
# Zeilen außerhalb dieses Fensters um den Abruftag gelten als Datumsfehler der Quelle
MAX_PAST_DAYS = 400
MAX_FUTURE_YEARS = 25


class SuspiciousFetch(Exception):
    pass


class ValidationFailed(Exception):
    pass


@dataclass
class Source:
    id: str
    stufe: int
    gebiet: dict  # gemeinde, ags, kreis, bundesland
    slug: str     # für die id, z. B. "berlin"


def iso_utc(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def local_date(t: dt.datetime) -> dt.date:
    return t.astimezone(TZ).date()


class Store:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.events: dict[str, dict] = {}  # schluessel -> Ereignis
        for f in sorted((self.dir / "events").glob("*/*.json")):
            for e in json.loads(f.read_text(encoding="utf-8"))["events"]:
                self.events[e["schluessel"]] = e

    # --- Merge ----------------------------------------------------------------------------------
    def ingest(self, rows, src: Source, fetched_at: dt.datetime, url: str, art: str, geo: Geo) -> dict:
        """Übernimmt einen Abruf. rows: Zeilen eines Adapters (radar.sources.*.Row)."""
        today = local_date(fetched_at)
        stamp = iso_utc(fetched_at)

        # Ortsname -> PLZ aus allem, was bekannt ist, für Einträge ohne PLZ (Aufzüge)
        place_plz: dict[str, Counter] = defaultdict(Counter)
        for e in self.events.values():
            o = e["ort"]
            if o["plz"] and not o["plz_abgeleitet"]:
                place_plz[N.place_key(o["bezeichnung"])][o["plz"]] += len(e["termine"])
        for r in rows:
            if r.plz and r.ort:
                place_plz[N.place_key(r.ort)][r.plz] += 1

        # Offensichtliche Tippfehler im Datum (etwa 2926 statt 2026) verwerfen
        lo, hi = today - dt.timedelta(days=MAX_PAST_DAYS), today + dt.timedelta(days=365 * MAX_FUTURE_YEARS)
        kept = [r for r in rows if lo <= r.datum <= hi]
        dropped = len(rows) - len(kept)
        rows = kept

        groups: dict[str, dict] = {}
        for r in rows:
            titel, turnus = N.split_title(r.thema)
            key = N.schluessel(src.id, titel, r.plz, r.ort, r.von, r.bis, r.route)
            g = groups.setdefault(key, {"row": r, "titel": titel, "turnus": turnus, "tage": set()})
            g["tage"].add(r.datum.isoformat())

        # Plausibilität vor jeder Änderung: verschwinden zu viele bekannte künftige Termine, abbrechen
        known_future = {(k, d) for k, e in self.events.items() if src.id in _source_ids(e)
                        for d in e["termine"] if d >= today.isoformat() and d not in e["entfernte_termine"]}
        listed = {(k, d) for k, g in groups.items() for d in g["tage"] if d >= today.isoformat()}
        if known_future and len(known_future & listed) < MIN_SHARE * len(known_future):
            raise SuspiciousFetch(f"{src.id}: nur {len(known_future & listed)} von {len(known_future)} "
                                  f"bekannten künftigen Terminen im Abruf {stamp}")

        stats = Counter()
        for key, g in groups.items():
            e = self.events.get(key)
            if e is None:
                e = self._new(key, g, src, geo, place_plz)
                self.events[key] = e
                stats["neu"] += 1
            else:
                stats["bekannt"] += 1
            tage = set(e["termine"]) | g["tage"]
            e["termine"] = sorted(tage)
            e["entfernte_termine"] = sorted(set(e["entfernte_termine"]) - g["tage"])
            e["zuletzt_gesehen"] = max(e["zuletzt_gesehen"], today.isoformat())
            e["zuerst_gesehen"] = min(e["zuerst_gesehen"], today.isoformat())
            self._touch_source(e, src, url, art, stamp)
            self._derive(e, g["row"])

        # Künftige Termine, die nicht mehr gelistet sind, als entfernt markieren
        for key, e in self.events.items():
            if src.id not in _source_ids(e):
                continue
            listed_days = groups[key]["tage"] if key in groups else set()
            gone = [d for d in e["termine"] if d >= today.isoformat() and d not in listed_days
                    and d not in e["entfernte_termine"]]
            if gone:
                e["entfernte_termine"] = sorted(set(e["entfernte_termine"]) | set(gone))
                stats["entfernte_termine"] += len(gone)
        stats["zeilen"] = len(rows) + dropped
        if dropped:
            stats["verworfen"] = dropped
        return dict(stats)

    def _new(self, key, g, src: Source, geo: Geo, place_plz) -> dict:
        r = g["row"]
        ort = r.ort or N.route_start(r.route)
        plz, derived = r.plz, False
        if not plz and ort:
            k = N.place_key(ort)
            if k not in place_plz and "/" in k:
                k = N.place_key(k.split("/")[0])
            if place_plz.get(k):
                plz, derived = place_plz[k].most_common(1)[0][0], True
        loc = geo.locate(plz, ort) if plz else {"lat": None, "lon": None, "bezirk": None}
        first = min(g["tage"])
        return {
            "id": f"{first}-{src.slug}-{plz or '00000'}-{key[:4]}",
            "schluessel": key,
            "titel": g["titel"], "turnus": g["turnus"],
            "kategorie": "Sonstiges", "form": "Kundgebung",
            "start": "", "ende": "", "termine": [], "entfernte_termine": [],
            "ort": {"bezeichnung": ort, "plz": plz, "plz_abgeleitet": derived, **src.gebiet,
                    "bezirk": loc["bezirk"], "lat": loc["lat"], "lon": loc["lon"],
                    "genauigkeit": "plz" if loc["lat"] is not None else "gemeinde"},
            "route": r.route or None,
            "veranstalter": None,
            "teilnehmer": {"angemeldet": None, "polizei": None, "veranstalter": None},
            "status": "angezeigt", "konfidenz": 0.95 if src.stufe == 1 else 0.6 if src.stufe == 2 else 0.4,
            "quellen": [],
            "zuerst_gesehen": "9999-12-31", "zuletzt_gesehen": "0000-01-01",
        }

    @staticmethod
    def _touch_source(e, src: Source, url, art, stamp):
        for q in e["quellen"]:
            if q["id"] == src.id:
                if stamp >= q["abgerufen"]:
                    q.update(url=url, art=art, abgerufen=stamp)
                q["erstmals"] = min(q["erstmals"], stamp)
                return
        e["quellen"].append({"id": src.id, "url": url, "stufe": src.stufe, "art": art, "abgerufen": stamp, "erstmals": stamp})

    @staticmethod
    def _derive(e, r):
        """Felder, die sich aus Titel und Terminen ableiten und bei Regeländerungen neu berechnet werden."""
        e["kategorie"] = N.kategorie(e["titel"])
        e["form"] = N.form(e["titel"], e["route"] or "")
        e["start"], e["ende"] = N.start_ende(dt.date.fromisoformat(e["termine"][0]), r.von, r.bis)

    # --- Status und Ausgabe -----------------------------------------------------------------------
    @staticmethod
    def status(e: dict, today: dt.date) -> str:
        """Ohne Nachlauf (Bauphase 3) gibt es nur 'angezeigt' (künftiger Termin gelistet) oder 'unklar'."""
        active = [d for d in e["termine"] if d >= today.isoformat() and d not in e["entfernte_termine"]]
        return "angezeigt" if active else "unklar"

    def validate(self) -> None:
        errors = []
        for e in self.events.values():
            for err in _validator.iter_errors(e):
                errors.append(f"{e.get('id')}: {'/'.join(map(str, err.path))}: {err.message}")
        if errors:
            raise ValidationFailed(f"{len(errors)} Fehler, erster: {errors[0]}")

    def write(self, today: dt.date) -> dict:
        """Schreibt alle Monatsdateien neu. Validiert vorher; bei Fehlern bleibt der alte Stand liegen."""
        for e in self.events.values():
            e["status"] = self.status(e, today)
        self.validate()
        months: dict[str, list] = defaultdict(list)
        for e in self.events.values():
            for m in sorted({d[:7] for d in e["termine"]}):
                months[m].append(e)
        out_dir = self.dir / "events"
        keep = set()
        for m, evs in months.items():
            f = out_dir / m[:4] / f"{m[5:]}.json"
            f.parent.mkdir(parents=True, exist_ok=True)
            evs.sort(key=lambda e: (e["start"], e["id"]))
            _dump_month(f, m, evs)
            keep.add(f)
        for f in out_dir.glob("*/*.json"):
            if f not in keep:
                f.unlink()
        index = {"monate": {m: len(v) for m, v in sorted(months.items())}, "ereignisse": len(self.events)}
        _dump(out_dir / "index.json", index)
        return index


def _source_ids(e: dict) -> set[str]:
    return {q["id"] for q in e["quellen"]}


def _dump_month(path: Path, month: str, events: list) -> None:
    """Ein Ereignis pro Zeile: kleine Dateien, lesbare Diffs."""
    lines = ",\n".join(json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in events)
    path.write_text(f'{{"monat":"{month}","anzahl":{len(events)},"events":[\n{lines}\n]}}\n', encoding="utf-8")


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
