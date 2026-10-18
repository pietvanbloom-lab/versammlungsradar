"""Rohabrufe im privaten Repo versammlungsradar-raw: gzip, nur bei geändertem Inhalt.

Ob sich etwas geändert hat, entscheidet der Fingerabdruck der geparsten Zeilen, nicht die HTML-Datei:
Die Seite enthält wechselnde Teile (Sitzungs-IDs, Banner), die sonst jeden Abruf als neu zählen ließen.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path


def fingerprint(rows) -> str:
    canon = [[r.datum.isoformat(), r.von, r.bis, r.thema, r.plz, r.ort, r.route] for r in rows]
    return hashlib.sha256(json.dumps(canon, ensure_ascii=False).encode()).hexdigest()


def save(repo: Path, source_id: str, fetched_at: dt.datetime, content: bytes, rows, url: str) -> Path | None:
    """Legt den Abruf ab, wenn sich die Zeilen seit dem letzten gespeicherten Abruf geändert haben."""
    base = Path(repo) / source_id
    latest_f = base / "latest.json"
    fp = fingerprint(rows)
    if latest_f.exists() and json.loads(latest_f.read_text())["sha256"] == fp:
        return None
    t = fetched_at.astimezone(dt.timezone.utc)
    f = base / t.strftime("%Y") / t.strftime("%m") / (t.strftime("%Y%m%dT%H%MZ") + ".html.gz")
    f.parent.mkdir(parents=True, exist_ok=True)
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    f.write_bytes(gzip.compress(content, mtime=0))
    latest_f.write_text(json.dumps({"sha256": fp, "datei": str(f.relative_to(base)), "abgerufen": t.strftime("%Y-%m-%dT%H:%MZ"),
                                    "url": url, "zeilen": len(rows)}, ensure_ascii=False, indent=1) + "\n")
    return f
