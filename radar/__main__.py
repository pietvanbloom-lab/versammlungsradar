"""Kommandozeile: python -m radar ingest | backfill | site | validate"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from . import http, rawstore
from .geo import Geo
from .site import build_site
from .sources import berlin
from .store import Source, Store, SuspiciousFetch, ValidationFailed, iso_utc, local_date

SOURCES = {"berlin": (berlin, Source(berlin.SOURCE_ID, berlin.STUFE, berlin.GEBIET, "berlin"))}
WAYBACK = "https://web.archive.org/web/{ts}/{url}"


def _json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def log_fetch(data: Path, source_id: str, fetched_at: dt.datetime, rows: int, art: str, url: str):
    f = data / "abrufe" / f"{source_id}.json"
    log = _json(f, [])
    stamp = iso_utc(fetched_at)
    if not any(x["zeit"] == stamp for x in log):
        log.append({"zeit": stamp, "art": art, "zeilen": rows, "url": url})
        log.sort(key=lambda x: x["zeit"])
    _dump(f, log)


def update_health(data: Path, source_id: str, when: dt.datetime, ok: bool, **kw):
    f = data / "health.json"
    h = _json(f, {})
    s = h.setdefault(source_id, {"letzter_versuch": None, "letzter_erfolg": None, "fehler": None, "zeilen": None, "fehler_in_folge": 0})
    s["letzter_versuch"] = iso_utc(when)
    if ok:
        s.update(letzter_erfolg=iso_utc(when), fehler=None, fehler_in_folge=0, **kw)
    else:
        s.update(fehler=kw.get("fehler"), fehler_in_folge=s.get("fehler_in_folge", 0) + 1)
    _dump(f, h)


def last_fetch_date(data: Path) -> dt.date:
    stamps = [x["zeit"] for f in (data / "abrufe").glob("*.json") for x in _json(f, [])]
    t = dt.datetime.strptime(max(stamps), "%Y-%m-%dT%H:%MZ").replace(tzinfo=dt.timezone.utc)
    return local_date(t)


def cmd_ingest(a) -> int:
    mod, src = SOURCES[a.source]
    data, geo = Path(a.data), Geo.load(Path(a.geo))
    if a.file:
        content = Path(a.file).read_bytes()
        fetched_at = dt.datetime.fromisoformat(a.fetched_at.replace("Z", "+00:00"))
    else:
        fetched_at = dt.datetime.now(dt.timezone.utc)
        try:
            content = http.fetch(mod.URL)
        except Exception as ex:  # Netz, robots.txt, HTTP-Fehler: Health melden, alten Stand behalten
            update_health(data, src.id, fetched_at, False, fehler=f"Abruf: {ex}")
            print(f"Abruf fehlgeschlagen: {ex}", file=sys.stderr)
            return 1
    url = a.url or mod.URL
    if not mod.has_table(content):
        update_health(data, src.id, fetched_at, False, fehler="Keine Versammlungstabelle auf der Seite")
        print("Keine Versammlungstabelle gefunden", file=sys.stderr)
        return 1
    rows = mod.parse(content)
    store = Store(data)
    try:
        stats = store.ingest(rows, src, fetched_at, url, a.art, geo)
        index = store.write(local_date(fetched_at))
    except (SuspiciousFetch, ValidationFailed) as ex:
        update_health(data, src.id, fetched_at, False, fehler=str(ex))
        print(ex, file=sys.stderr)
        return 1
    log_fetch(data, src.id, fetched_at, len(rows), a.art, url)
    update_health(data, src.id, fetched_at, True, zeilen=len(rows), ereignisse=index["ereignisse"])
    saved = rawstore.save(Path(a.raw_repo), src.id, fetched_at, content, rows, url) if a.raw_repo else None
    print(json.dumps({"abgerufen": iso_utc(fetched_at), **stats, "ereignisse": index["ereignisse"],
                      "rohabruf": str(saved) if saved else None}, ensure_ascii=False))
    return 0


def cmd_backfill(a) -> int:
    """Wayback-Snapshots chronologisch durch denselben Merge schicken wie Live-Abrufe."""
    mod, src = SOURCES[a.source]
    data, geo = Path(a.data), Geo.load(Path(a.geo))
    store = Store(data)
    last = None
    for f in sorted(Path(a.snapshots).glob("*.html")):
        ts = f.stem
        if not re.fullmatch(r"\d{14}", ts):
            continue
        content = f.read_bytes()
        if not mod.has_table(content):
            print(f"{ts}: keine Tabelle, übersprungen")
            continue
        fetched_at = dt.datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)
        url = WAYBACK.format(ts=ts, url=mod.URL.replace("index.php", ""))
        rows = mod.parse(content)
        try:
            stats = store.ingest(rows, src, fetched_at, url, "archiv", geo)
        except SuspiciousFetch as ex:
            print(f"{ts}: {ex}, übersprungen")
            continue
        log_fetch(data, src.id, fetched_at, len(rows), "archiv", url)
        if a.raw_repo:
            rawstore.save(Path(a.raw_repo), src.id, fetched_at, content, rows, url)
        last = fetched_at
        print(f"{ts}: {stats}")
    if last:
        print(store.write(local_date(last)))
    return 0


def cmd_site(a) -> int:
    build_site(Path(a.data), Path(a.template), Path(a.out), last_fetch_date(Path(a.data)), Path(a.geo))
    print(a.out)
    return 0


def cmd_validate(a) -> int:
    store = Store(Path(a.data))
    try:
        store.validate()
    except ValidationFailed as ex:
        print(ex, file=sys.stderr)
        return 1
    print(f"{len(store.events)} Ereignisse gültig")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="radar")
    p.add_argument("--data", default="data")
    p.add_argument("--geo", default="raw", help="Ordner mit plz.csv, bezirke.json, laender.json")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("ingest", help="Quelle abrufen (oder Datei einlesen) und in den Store übernehmen")
    i.add_argument("--source", default="berlin", choices=SOURCES)
    i.add_argument("--file", help="gespeicherter Abruf statt Live-Abruf")
    i.add_argument("--fetched-at", help="Abrufzeit der Datei, ISO 8601")
    i.add_argument("--url", help="Beleg-URL der Datei (Standard: Quell-URL)")
    i.add_argument("--art", default="aktuell", choices=["aktuell", "archiv"])
    i.add_argument("--raw-repo", help="Checkout von versammlungsradar-raw")
    i.set_defaults(func=cmd_ingest)

    b = sub.add_parser("backfill", help="Wayback-Snapshots (JJJJMMTThhmmss.html) übernehmen")
    b.add_argument("--source", default="berlin", choices=SOURCES)
    b.add_argument("--snapshots", required=True)
    b.add_argument("--raw-repo")
    b.set_defaults(func=cmd_backfill)

    s = sub.add_parser("site", help="Statische Seite aus dem Store bauen")
    s.add_argument("--template", default="prototype/template.html")
    s.add_argument("--out", default="site/versammlungsradar.html")
    s.set_defaults(func=cmd_site)

    v = sub.add_parser("validate", help="Alle Ereignisse gegen schema/event.schema.json prüfen")
    v.set_defaults(func=cmd_validate)

    a = p.parse_args(argv)
    if a.cmd == "ingest" and a.file and not a.fetched_at:
        p.error("--file braucht --fetched-at")
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
