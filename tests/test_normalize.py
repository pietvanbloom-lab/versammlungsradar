import datetime as dt

from radar import normalize as N


def test_turnus_abgetrennt():
    t, turnus = N.split_title("Gegen Mietverdrängung (vom 03.10. bis 02.12.2026 - jeweils Mi.,Sa.,So.)")
    assert t == "Gegen Mietverdrängung"
    assert turnus == "vom 03.10. bis 02.12.2026 - jeweils Mi.,Sa.,So."


def test_praefixe_entfernt():
    assert N.split_title(",,Protest gegen Hinrichtungen")[0] == "Protest gegen Hinrichtungen"
    assert N.split_title("Thema: Muslime für Frieden")[0] == "Muslime für Frieden"


def test_klammer_im_titel_bleibt():
    assert N.split_title("Gedenken (Hiroshima-Tag)")[0] == "Gedenken (Hiroshima-Tag)"


def test_kategorie_und_form():
    assert N.kategorie("Kundgebung für sicheres Radfahren") == "Verkehr"
    assert N.kategorie("Gegen Mietverdrängung") == "Wohnen"
    assert N.kategorie("Lesen gegen das Vergessen") == "Sonstiges"
    assert N.form("Mahnwache für die Opfer", "") == "Mahnwache"
    assert N.form("Demo", "Pariser Platz - Unter den Linden") == "Aufzug"


def test_start_ende_mit_zeitzone():
    s, e = N.start_ende(dt.date(2026, 10, 11), "14:00", "18:00")
    assert (s, e) == ("2026-10-11T14:00+02:00", "2026-10-11T18:00+02:00")
    s, e = N.start_ende(dt.date(2026, 12, 31), "22:00", "02:00")
    assert (s, e) == ("2026-12-31T22:00+01:00", "2027-01-01T02:00+01:00")


def test_ortsschluessel():
    assert N.place_key("Neu: Bebelplatz (AP)") == "bebelplatz"
    assert N.place_key("Unter den Linden 77") == "unter den linden"
    assert N.route_start("Neu: Invalidenpark (AP) - Invalidenstr. - Luisenstr.") == "Invalidenpark (AP)"


def test_schluessel_stabil():
    a = N.schluessel("q", "Titel", "10117", "Pariser Platz", "10:00", "12:00", "")
    assert a == N.schluessel("q", "titel", "10117", "pariser platz", "10:00", "12:00", "")
    assert a != N.schluessel("q", "Titel", "10117", "Pariser Platz", "11:00", "12:00", "")
