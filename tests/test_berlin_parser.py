"""Berlin-Adapter gegen den gespeicherten Abruf vom 17.10.2026, 20:03 UTC."""
import datetime as dt
import gzip

from radar.sources import berlin


def test_alle_zeilen(snapshot_rows):
    assert len(snapshot_rows) == 1139


def test_erste_zeile(snapshot_rows):
    r = snapshot_rows[0]
    assert r.datum == dt.date(2026, 10, 17)
    assert (r.von, r.bis) == ("00:00", "23:59")
    assert r.thema.startswith("Sitzstreik und Mahnwache für Menschenrechte im Iran")
    assert (r.plz, r.ort, r.route) == ("10557", "Platz der Republik 1", "")


def test_zeitraum(snapshot_rows):
    tage = [r.datum for r in snapshot_rows]
    assert min(tage) == dt.date(2026, 10, 17)
    assert max(tage) == dt.date(2034, 8, 17)


def test_zellen_ohne_html_und_entities(snapshot_rows):
    for r in snapshot_rows:
        for v in (r.thema, r.ort, r.route):
            assert "<" not in v and "&amp;" not in v and "  " not in v


def test_zeilen_ohne_plz(snapshot_rows):
    """Ohne PLZ steht entweder eine Aufzugsstrecke da, oder die Liste nennt gar keinen Ort."""
    ohne_plz = [r for r in snapshot_rows if not r.plz]
    assert len(ohne_plz) == 182
    assert sum(1 for r in ohne_plz if r.route) == 117
    assert all(r.route or not r.ort for r in ohne_plz)


def test_uhrzeiten_formatiert(snapshot_rows):
    for r in snapshot_rows:
        assert len(r.von) == 5 and r.von[2] == ":"


def test_gzip_wie_wayback(snapshot_bytes):
    assert len(berlin.parse(gzip.compress(snapshot_bytes))) == 1139


def test_tabelle_erkannt(snapshot_bytes):
    assert berlin.has_table(snapshot_bytes)
    assert not berlin.has_table("<html><body>Wartungsarbeiten</body></html>")
