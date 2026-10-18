"""Merge, Monatsdateien und Schema-Prüfung."""
import datetime as dt
import json

import pytest

from radar.sources import berlin
from radar.store import Store, SuspiciousFetch, ValidationFailed
from tests.conftest import SNAPSHOT_AT, page

UTC = dt.timezone.utc
URL = berlin.URL


def at(y, m, d, h=7):
    return dt.datetime(y, m, d, h, 0, tzinfo=UTC)


def ingest(store, src, geo, rows, when):
    return store.ingest(berlin.parse(page(rows)), src, when, URL, "aktuell", geo)


A = ("20.10.2026", "10:00", "12:00", "Kundgebung für sicheres Radfahren", "10117", "Pariser Platz", "")
B = ("21.10.2026", "18:00", "19:00", "Mahnwache (vom 21.10. bis 22.10.2026 - täglich)", "10557", "Platz der Republik 1", "")
B2 = ("22.10.2026", "18:00", "19:00", "Mahnwache (vom 21.10. bis 22.10.2026 - täglich)", "10557", "Platz der Republik 1", "")
ZUG = ("20.10.2026", "14:00", "16:00", "Aufzug ohne PLZ", "", "", "Neu: Pariser Platz (AP) - Unter den Linden")


def test_snapshot_wird_gueltig_gespeichert(tmp_path, src, geo, snapshot_rows):
    store = Store(tmp_path)
    stats = store.ingest(snapshot_rows, src, SNAPSHOT_AT, URL, "aktuell", geo)
    assert stats["neu"] == len(store.events) and stats["zeilen"] == 1139
    # jede Zeile der Liste landet als Termin in genau einem Ereignis
    assert sum(len(e["termine"]) for e in store.events.values()) == len({(r.datum, r.von, r.bis, r.thema, r.plz, r.ort, r.route) for r in snapshot_rows})
    index = store.write(dt.date(2026, 10, 17))
    assert index["ereignisse"] == len(store.events)
    assert (tmp_path / "events" / "2026" / "10.json").exists()
    assert (tmp_path / "events" / "2034" / "08.json").exists()
    assert Store(tmp_path).events.keys() == store.events.keys()


def test_wiederholter_abruf_aendert_nichts(tmp_path, src, geo, snapshot_rows):
    s1 = Store(tmp_path)
    s1.ingest(snapshot_rows, src, SNAPSHOT_AT, URL, "aktuell", geo)
    s1.write(dt.date(2026, 10, 17))
    before = {f.name + f.parent.name: f.read_text() for f in (tmp_path / "events").rglob("*.json")}
    s2 = Store(tmp_path)
    stats = s2.ingest(snapshot_rows, src, SNAPSHOT_AT, URL, "aktuell", geo)
    s2.write(dt.date(2026, 10, 17))
    after = {f.name + f.parent.name: f.read_text() for f in (tmp_path / "events").rglob("*.json")}
    assert stats.get("neu", 0) == 0 and before == after


def test_wiederkehrender_termin_ist_ein_ereignis(tmp_path, src, geo):
    store = Store(tmp_path)
    ingest(store, src, geo, [A, B, B2], at(2026, 10, 19))
    mahnwache = [e for e in store.events.values() if e["titel"] == "Mahnwache"]
    assert len(mahnwache) == 1
    e = mahnwache[0]
    assert e["termine"] == ["2026-10-21", "2026-10-22"]
    assert e["turnus"] == "vom 21.10. bis 22.10.2026 - täglich"
    assert e["form"] == "Mahnwache"
    assert e["start"] == "2026-10-21T18:00+02:00"


def test_id_bleibt_und_vergangenes_bleibt(tmp_path, src, geo):
    store = Store(tmp_path)
    ingest(store, src, geo, [A, B, B2], at(2026, 10, 19))
    ids = {k: e["id"] for k, e in store.events.items()}
    # zwei Tage später: A und der erste Mahnwachen-Tag sind vorbei und nicht mehr gelistet
    ingest(store, src, geo, [B2], at(2026, 10, 22))
    assert {k: e["id"] for k, e in store.events.items()} == ids
    a = next(e for e in store.events.values() if e["titel"].startswith("Kundgebung"))
    assert a["termine"] == ["2026-10-20"] and a["entfernte_termine"] == []
    m = next(e for e in store.events.values() if e["titel"] == "Mahnwache")
    assert m["termine"] == ["2026-10-21", "2026-10-22"] and m["entfernte_termine"] == []
    assert m["zuletzt_gesehen"] == "2026-10-22" and a["zuletzt_gesehen"] == "2026-10-19"


def test_entfernter_kuenftiger_termin(tmp_path, src, geo):
    store = Store(tmp_path)
    ingest(store, src, geo, [A, B, B2], at(2026, 10, 19))
    ingest(store, src, geo, [A, B], at(2026, 10, 19, 13))
    m = next(e for e in store.events.values() if e["titel"] == "Mahnwache")
    assert m["entfernte_termine"] == ["2026-10-22"]
    assert Store.status(m, dt.date(2026, 10, 22)) == "unklar"
    assert Store.status(m, dt.date(2026, 10, 21)) == "angezeigt"
    # taucht der Termin wieder auf, gilt er wieder
    ingest(store, src, geo, [A, B, B2], at(2026, 10, 19, 19))
    assert m["entfernte_termine"] == []


def test_verdaechtiger_abruf_wird_abgelehnt(tmp_path, src, geo, snapshot_rows):
    store = Store(tmp_path)
    store.ingest(snapshot_rows, src, SNAPSHOT_AT, URL, "aktuell", geo)
    with pytest.raises(SuspiciousFetch):
        store.ingest(snapshot_rows[:100], src, SNAPSHOT_AT + dt.timedelta(hours=6), URL, "aktuell", geo)
    assert all(not e["entfernte_termine"] for e in store.events.values())


def test_aufzug_ohne_plz_bekommt_startpunkt_und_abgeleitete_plz(tmp_path, src, geo):
    store = Store(tmp_path)
    ingest(store, src, geo, [A, ZUG], at(2026, 10, 19))
    z = next(e for e in store.events.values() if e["form"] == "Aufzug")
    assert z["ort"]["bezeichnung"] == "Pariser Platz (AP)"
    assert z["ort"]["plz"] == "10117" and z["ort"]["plz_abgeleitet"] is True
    assert z["ort"]["bezirk"] == "Mitte" and z["ort"]["genauigkeit"] == "plz"


def test_monatsdateien_ereignis_ueber_monatsgrenze(tmp_path, src, geo):
    rows = [("31.10.2026", "18:00", "19:00", "Mahnwache", "10557", "Ort", ""),
            ("01.11.2026", "18:00", "19:00", "Mahnwache", "10557", "Ort", "")]
    store = Store(tmp_path)
    ingest(store, src, geo, rows, at(2026, 10, 19))
    store.write(dt.date(2026, 10, 19))
    okt = json.loads((tmp_path / "events/2026/10.json").read_text())["events"]
    nov = json.loads((tmp_path / "events/2026/11.json").read_text())["events"]
    assert [e["id"] for e in okt] == [e["id"] for e in nov]
    assert json.loads((tmp_path / "events/index.json").read_text())["monate"] == {"2026-10": 1, "2026-11": 1}


def test_schema_fehler_verhindert_schreiben(tmp_path, src, geo):
    store = Store(tmp_path)
    ingest(store, src, geo, [A], at(2026, 10, 19))
    next(iter(store.events.values()))["kategorie"] = "Gefährlich"
    with pytest.raises(ValidationFailed):
        store.write(dt.date(2026, 10, 19))
    assert not (tmp_path / "events").exists()


def test_keine_personendaten_felder(tmp_path, src, geo):
    store = Store(tmp_path)
    ingest(store, src, geo, [A], at(2026, 10, 19))
    e = next(iter(store.events.values()))
    assert e["veranstalter"] is None
    assert not {"anmelder", "name", "redner"} & set(e)


def test_datumsfehler_wird_verworfen(tmp_path, src, geo):
    store = Store(tmp_path)
    stats = ingest(store, src, geo, [A, ("05.01.2926", "10:00", "12:00", "Tippfehler", "10117", "Ort", "")], at(2026, 10, 19))
    assert stats["verworfen"] == 1 and len(store.events) == 1
