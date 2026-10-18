"""Adapter für die Versammlungsliste der Polizei Berlin (Stufe 1, amtlich, § 8 VersFG BE).

Die Liste ist eine HTML-Tabelle mit den Spalten Datum, Von, Bis, Thema, PLZ, Versammlungsort und
Aufzugsstrecke. Sie zeigt nur Termine ab dem Abruftag; jede Zeile ist ein Termin an einem Tag.
"""
from __future__ import annotations

import datetime as dt
import gzip
import html
import re
from dataclasses import dataclass

SOURCE_ID = "berlin-polizei-versammlungen"
URL = "https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege/index.php"
STUFE = 1
GEBIET = {"gemeinde": "Berlin", "ags": "11000000", "kreis": "Berlin", "bundesland": "BE"}

_ROW = re.compile(r'<tr class="(?:odd|even)[^"]*">(.*?)</tr>', re.S)
_CELL = re.compile(r'headers="(\w+)">(.*?)</td>', re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Row:
    datum: dt.date
    von: str
    bis: str
    thema: str
    plz: str
    ort: str
    route: str


def _text(v: str) -> str:
    return _WS.sub(" ", html.unescape(_TAG.sub("", v))).strip()


def decode(raw: bytes) -> str:
    """Wayback liefert die Seite teils gzip-komprimiert aus."""
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def parse(page: str | bytes) -> list[Row]:
    if isinstance(page, bytes):
        page = decode(page)
    rows = []
    for tr in _ROW.findall(page):
        c = {k: _text(v) for k, v in _CELL.findall(tr)}
        try:
            datum = dt.datetime.strptime(c.get("Datum", ""), "%d.%m.%Y").date()
        except ValueError:
            continue
        rows.append(Row(datum=datum, von=c.get("Von", ""), bis=c.get("Bis", ""), thema=c.get("Thema", ""),
                        plz=c.get("PLZ", ""), ort=c.get("Versammlungsort", ""), route=c.get("Aufzugsstrecke", "")))
    return rows


def has_table(page: str | bytes) -> bool:
    """Unterscheidet eine leere Liste von einer Seite ohne Tabelle (Fehlerseite, Umbau)."""
    if isinstance(page, bytes):
        page = decode(page)
    return 'id="searchresults-table"' in page
