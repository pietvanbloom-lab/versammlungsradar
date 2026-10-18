"""Statische Seite aus dem Store: kompaktes JSON (Wörterbücher, Tagesläufe) in das Template einbetten.

Bis zum Deploy auf Cloudflare Pages ist die Seite eine einzelne Datei. Danach lädt das Frontend die
Monatsdateien direkt (ARCHITEKTUR.md, Frontend).
"""
from __future__ import annotations

import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from .normalize import KATEGORIEN, TZ
from .store import Store

WINDOW = 365  # Tage zurück und voraus


def _dp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    dmax, k = 0.0, 0
    den = math.hypot(b[1] - a[1], b[0] - a[0]) or 1e-12
    for i in range(1, len(pts) - 1):
        p = pts[i]
        d = abs((b[1] - a[1]) * p[0] - (b[0] - a[0]) * p[1] + b[0] * a[1] - b[1] * a[0]) / den
        if d > dmax:
            dmax, k = d, i
    if dmax > eps:
        return _dp(pts[:k + 1], eps)[:-1] + _dp(pts[k:], eps)
    return [a, b]


def _outlines(path: Path, eps: float, nd: int) -> list:
    fc = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for f in fc["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = []
        for poly in polys:
            ring = poly[0]
            h = len(ring) // 2  # geschlossener Ring: Hälften getrennt vereinfachen
            r = _dp(ring[:h + 1], eps)[:-1] + _dp(ring[h:], eps)
            if len(r) >= 4:
                rings.append([[round(p[0], nd), round(p[1], nd)] for p in r])
        out.append({"n": f["properties"]["name"], "id": f["properties"].get("id"), "r": rings})
    return out


def compact(store: Store, fetches: list[dict], today: dt.date) -> dict:
    start, horizon = today - dt.timedelta(days=WINDOW), today + dt.timedelta(days=WINDOW)
    dn = lambda s: (dt.date.fromisoformat(s[:10]) - start).days
    dicts, idx = defaultdict(list), defaultdict(dict)

    def ref(name, v):
        if v not in idx[name]:
            idx[name][v] = len(dicts[name])
            dicts[name].append(v)
        return idx[name][v]

    rows = []
    for e in sorted(store.events.values(), key=lambda e: (e["start"], e["id"])):
        days = [dn(d) for d in e["termine"] if d not in e["entfernte_termine"] and start.isoformat() <= d <= horizon.isoformat()]
        if not days:
            continue
        runs = []
        for d in days:
            if runs and runs[-1][0] + runs[-1][1] == d:
                runs[-1][1] += 1
            else:
                runs.append([d, 1])
        q = max(e["quellen"], key=lambda q: q["abgerufen"])
        o = e["ort"]
        thema = e["titel"] + (f" ({e['turnus']})" if e["turnus"] else "")
        rows.append([e["id"][-4:], ref("txt", thema), ref("txt", e["titel"]) if e["titel"] != thema else -1,
                     KATEGORIEN.index(e["kategorie"]), ref("form", e["form"]), e["start"][11:16], e["ende"][11:16], runs,
                     o["plz"], ref("ort", o["bezeichnung"]), ref("bez", o["bezirk"] or "unbekannt"), o["lat"], o["lon"],
                     ref("txt", e["route"]) if e["route"] else -1, 1 if o["plz_abgeleitet"] else 0,
                     ref("src", (q["url"], q["abgerufen"], q["art"])), dn(e["zuerst_gesehen"]), dn(e["zuletzt_gesehen"]), e["id"]])

    fdays = sorted({f["zeit"][:10] for f in fetches})
    gaps, d = [], start
    while d < today:
        prev = [x for x in fdays if x <= d.isoformat()]
        if not prev or (d - dt.date.fromisoformat(prev[-1])).days > 7:
            gaps.append(d.isoformat())
        d += dt.timedelta(days=1)
    current = [f for f in fetches if f["art"] == "aktuell"]
    last = current[-1] if current else fetches[-1]
    last_t = dt.datetime.strptime(last["zeit"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=dt.timezone.utc)
    future = [d for e in store.events.values() if e["status"] == "angezeigt" for d in e["termine"] if d not in e["entfernte_termine"]]
    meta = {"start": start.isoformat(), "today": today.isoformat(), "horizon": horizon.isoformat(),
            "stand_zeit": last_t.astimezone(TZ).strftime("%H:%M"),
            "snapshots": sum(1 for f in fetches if f["art"] == "archiv"), "abrufe": len(current),
            "events": len(rows), "gaps": gaps, "current_rows": last["zeilen"],
            "current_max": max(future) if future else today.isoformat()}
    return {"meta": meta, "cats": KATEGORIEN, "dict": dict(dicts), "E": rows}


def build_site(data: Path, template: Path, out: Path, today: dt.date, geo_dir: Path) -> None:
    store = Store(data)
    for e in store.events.values():
        e["status"] = Store.status(e, today)
    fetches = sorted((x for f in (data / "abrufe").glob("*.json") for x in json.loads(f.read_text(encoding="utf-8"))),
                     key=lambda x: x["zeit"])
    payload = compact(store, fetches, today)
    payload["laender"] = _outlines(geo_dir / "laender.json", 0.02, 3)
    payload["bezirke"] = _outlines(geo_dir / "bezirke.json", 0.0008, 4)
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template.read_text(encoding="utf-8").replace("/*DATA*/", js), encoding="utf-8")
