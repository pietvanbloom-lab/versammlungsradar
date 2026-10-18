"""Ortszuordnung ohne Geocoding-Dienst: PLZ-Mittelpunkt, Berliner Bezirk per Punkt-in-Polygon.

Die Geodaten liegen nicht im Repo (Lizenzen der Quellen), scripts/fetch_geo.sh lädt sie nach raw/.
Genauigkeit ist deshalb immer "plz". Nominatim mit Cache folgt in Bauphase 3.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _pip(x: float, y: float, ring: list) -> bool:
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi:
            inside = not inside
        j = i
    return inside


class Geo:
    def __init__(self, plz: dict[str, tuple[float, float]], bezirke: list[tuple[str, list]]):
        self.plz = plz
        self.bezirke = bezirke  # (Name, [Ring, ...]) mit Ringen aus [lon, lat]

    @classmethod
    def load(cls, raw_dir: Path) -> "Geo":
        plz = {}
        for line in (raw_dir / "plz.csv").read_text(encoding="utf-8").splitlines()[1:]:
            p, la, lo = line.split(",")
            plz[p.strip()] = (float(la), float(lo))
        fc = json.loads((raw_dir / "bezirke.json").read_text(encoding="utf-8"))
        bez = []
        for f in fc["features"]:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            bez.append((f["properties"]["name"], [p[0] for p in polys]))
        return cls(plz, bez)

    def bezirk(self, lat: float, lon: float) -> str | None:
        for name, rings in self.bezirke:
            if any(_pip(lon, lat, r) for r in rings):
                return name
        # PLZ-Mittelpunkte am Stadtrand liegen manchmal knapp außerhalb: nächster Bezirk
        best, bd = None, float("inf")
        for name, rings in self.bezirke:
            for r in rings:
                for p in r[::5]:
                    d = (p[0] - lon) ** 2 + (p[1] - lat) ** 2
                    if d < bd:
                        best, bd = name, d
        return best

    def locate(self, plz: str, ort: str) -> dict:
        """lat/lon am PLZ-Mittelpunkt, leicht gestreut (fest je Ort), damit Punkte nicht übereinanderliegen."""
        ll = self.plz.get(plz)
        if not ll:
            return {"lat": None, "lon": None, "bezirk": None}
        lat, lon = ll
        h = hashlib.md5((ort.lower() + plz).encode()).digest()
        a = h[0] / 255 * 2 * math.pi
        r = (h[1] / 255) ** 0.5 * 0.0035
        return {"lat": round(lat + r * math.sin(a), 5),
                "lon": round(lon + r * math.cos(a) / math.cos(math.radians(lat)), 5),
                "bezirk": self.bezirk(lat, lon)}
