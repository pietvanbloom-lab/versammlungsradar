import datetime as dt
import gzip
from pathlib import Path

import pytest

from radar.geo import Geo
from radar.sources import berlin
from radar.store import Source

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOT_AT = dt.datetime(2026, 10, 17, 20, 3, tzinfo=dt.timezone.utc)


@pytest.fixture(scope="session")
def snapshot_bytes() -> bytes:
    return gzip.decompress((FIXTURES / "berlin-20261017T2003Z.html.gz").read_bytes())


@pytest.fixture(scope="session")
def snapshot_rows(snapshot_bytes):
    return berlin.parse(snapshot_bytes)


@pytest.fixture
def src() -> Source:
    return Source(berlin.SOURCE_ID, berlin.STUFE, berlin.GEBIET, "berlin")


@pytest.fixture
def geo() -> Geo:
    """Kleine Geodaten ohne Netz: zwei PLZ, ein Quadrat als 'Mitte'."""
    square = [[13.3, 52.4], [13.5, 52.4], [13.5, 52.6], [13.3, 52.6], [13.3, 52.4]]
    return Geo({"10117": (52.517, 13.389), "10557": (52.520, 13.370)}, [("Mitte", [square])])


def page(rows: list[tuple]) -> str:
    """Baut eine Seite im Format der Berliner Liste. rows: (datum, von, bis, thema, plz, ort, route)."""
    trs = "".join(
        f'<tr class="odd line_1"><td class="text" headers="Datum">{d}</td><td class="text" headers="Von">{v}</td>'
        f'<td class="text" headers="Bis">{b}</td><td class="text" headers="Thema">{t}</td><td class="text" headers="PLZ">{p}</td>'
        f'<td class="text" headers="Versammlungsort">{o}</td><td class="text" headers="Aufzugsstrecke">{r}</td></tr>'
        for d, v, b, t, p, o, r in rows)
    return f'<table id="searchresults-table"><tbody>{trs}</tbody></table>'
