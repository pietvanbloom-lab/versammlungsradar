"""Normalisierung: Titel und Turnus, Form, Kategorie, Zeiten, Ortsschlüssel.

Kategorie und Form kommen bis Bauphase 3 aus festen Stichwortregeln. Danach übernimmt ein Modell
mit fester Liste, das nur den Titel sieht (ARCHITEKTUR.md, Schritt 5).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")

KATEGORIEN = ["Arbeit", "Klima", "Frieden und Außenpolitik", "Migration", "Wohnen", "Verkehr", "Bildung",
              "Gesundheit", "Landwirtschaft", "Sonstiges"]
FORMEN = ["Aufzug", "Kundgebung", "Mahnwache", "Infostand"]

# Turnus-Zusatz der Berliner Liste, z. B. "(vom 03.10. bis 02.12.2026 - jeweils Mi.,Sa.,So.)"
_TURNUS = re.compile(r"\s*\(((?:vom|am|ab|jeweils)[^()]*)\)\s*$")

_KW = {
    "Arbeit": r"streik|tarif|lohn|löhne|gewerkschaft|ver\.?di|ig metall|beschäftigte|arbeitsplätz|arbeitnehm|arbeitsbeding|entlassung|kündigung|mindestlohn|bürgergeld|hartz|rente|sozialabbau|sozialkürz|kürzung|haushalt|betriebsrat|warnstreik|dgb|gew\b|evg|beamt|tvöd|tv-l|armut|sozialstaat|alleinerzieh|amazon",
    "Klima": r"klima|umwelt|fossil|kohle|erdgas|\bgas\b|energiewende|atomkraft|wald|bäume|baum|artenschutz|natur|letzte generation|fridays|extinction|greenpeace|biodivers|plastik|meere|emission|co2|erneuerbar",
    "Frieden und Außenpolitik": r"frieden|krieg|waffen|nato|ukrain|russland|russisch|israel|paläst|gaza|iran|syri|kurd|türkei|erdo|sudan|kongo|afghan|eritrea|tigray|armeni|aserbaid|bergkarabach|belarus|venezuela|china|tibet|uigur|hongkong|taiwan|kaschmir|pakistan|indien|bangladesch|hinrichtung|genozid|völkermord|botschaft|sanktion|rüstung|bundeswehr|wehrpflicht|militär|besatzung|libanon|jemen|irak|äthiop|nigeria|kamerun|myanmar|sri lanka|tamil|belutsch|vietnam|kuba|georgien|serbien|kosovo|bosnien|polen|ungarn|usa|trump|geisel|hamas|hisbollah|antisemit|zionis|intifada|westjordan|libyen|ägypten|marokko|westsahara|algerien|tunesien|mali|somalia|ruanda|nahost|militärdiktatur|diktatur|regime|außenpolitik|völkerrecht|un-\b|vereinte nationen|potsdamer abkommen|weltkrieg|abrüstung|drohne|cuba|kasach|pahlavi|palestin|genocid|korea|hiroshima|atombomb|kiew|kyjiw",
    "Migration": r"migration|migrant|flucht|flüchtl|geflüchtet|asyl|abschiebung|abschiebe|refugee|rassis|einbürger|bleiberecht|aufenthalt|grenze|seenot|remigration|zuwanderung|integration",
    "Wohnen": r"miet|wohn|verdrängung|räumung|obdach|zwangsräum|enteign|sanierung|gentrifiz|bauprojekt|kiez|leerstand|hausbesetz|bebauung",
    "Verkehr": r"fahrrad|radfahr|radweg|radverkehr|verkehr|autobahn|a100|a 100|tempo ?30|critical mass|öpnv|bvg|s-bahn|u-bahn|\bbahn\b|tram|parkplatz|fußgänger|fußverkehr|kidical|autofrei|tesla|lkw|taxi|uber|mobilität|ticket|kfz|motorrad",
    "Bildung": r"schul|kita|bildung|universit|hochschul|studier|student|lehrer|lehrkräft|erzieher|ausbildung|azubi|wissenschaft|forschung|bafög|\bfu\b|\btu\b|humboldt|schüler|prüfung",
    "Gesundheit": r"gesundheit|krankenhaus|kliniken|klinik|pflege|corona|impf|medizin|hebamme|charité|vivantes|patient|cannabis|psychi|abtreibung|schwangerschaft|219a|§ ?218|aids|hiv|drogen|sucht|ärzt|krankenkasse",
    "Landwirtschaft": r"landwirt|bauern|tierhaltung|massentier|agrar|tierschutz|tierrecht|tierversuch|tiere|\btier|vegan|pelz|schlacht|fleisch|milch|ernährung|gentechnik|glyphosat|pestizid|imker|bienen",
}
_KWC = {k: re.compile(v, re.I) for k, v in _KW.items()}


def split_title(thema: str) -> tuple[str, str | None]:
    """Trennt den Turnus-Zusatz ab und räumt Präfixe und verirrte Satzzeichen weg."""
    m = _TURNUS.search(thema)
    turnus = m.group(1).strip() if m else None
    t = _TURNUS.sub("", thema).strip().strip(",").strip()
    t = re.sub(r"^Thema:\s*", "", t, flags=re.I)
    t = t.lstrip(",;'\"„“ ").strip()
    return (t or "Ohne Thema"), turnus


def kategorie(titel: str) -> str:
    best, score = "Sonstiges", 0
    for k in KATEGORIEN[:-1]:
        n = len(_KWC[k].findall(titel))
        if n > score:
            best, score = k, n
    return best


def form(titel: str, route: str) -> str:
    if route:
        return "Aufzug"
    if re.search(r"mahnwache|gedenk", titel, re.I):
        return "Mahnwache"
    if re.search(r"infostand|info-stand|informationsstand", titel, re.I):
        return "Infostand"
    return "Kundgebung"


def start_ende(tag: dt.date, von: str, bis: str) -> tuple[str, str]:
    """ISO 8601 mit Zeitzone. Endet ein Termin vor seinem Beginn, liegt das Ende am Folgetag."""
    def at(d: dt.date, hm: str) -> dt.datetime:
        h, m = (int(x) for x in (hm or "00:00").split(":"))
        return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)
    s = at(tag, von)
    e = at(tag, bis or von)
    if e < s:
        e = at(tag + dt.timedelta(days=1), bis)
    return s.isoformat(timespec="minutes"), e.isoformat(timespec="minutes")


def place_key(ort: str) -> str:
    """Vergleichsschlüssel für Orte: ohne 'Neu:', Klammerzusätze, Hausnummer; 'straße' = 'str.'."""
    o = re.sub(r"^\s*Neu:\s*", "", ort)
    o = re.sub(r"\([^)]*\)", "", o)
    o = re.sub(r"\s+\d+[a-zA-Z]?(\s*-\s*\d+)?\s*$", "", o.strip())
    return re.sub(r"\s+", " ", o).strip().lower().replace("straße", "str.")


def route_start(route: str) -> str:
    """Startpunkt eines Aufzugs: erster Abschnitt der Strecke."""
    return re.sub(r"^\s*Neu:\s*", "", route.split(" - ")[0]).strip()


def schluessel(source_id: str, titel: str, plz: str, ort: str, von: str, bis: str, route: str) -> str:
    """Stabiler Schlüssel eines Ereignisses: gleiches Thema, gleicher Ort, gleiche Uhrzeit = ein Ereignis."""
    raw = "|".join([source_id, titel.lower(), plz, ort.lower(), von, bis, route.lower()])
    return hashlib.sha1(raw.encode()).hexdigest()[:12]
