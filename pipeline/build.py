"""Versammlungsradar-Prototyp: Berliner Liste (aktuell + Wayback) -> kompaktes Ereignis-JSON."""
import gzip, re, html, json, os, sys, glob, hashlib, math, datetime as dt, collections

S = sys.argv[1] if len(sys.argv) > 1 else "."  # Repo-Wurzel
TODAY = dt.date(2026, 10, 17)
START = TODAY - dt.timedelta(days=365)
HORIZON = TODAY + dt.timedelta(days=365)
LIST_URL = "https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege/index.php"
WB_URL = "https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege/"

def parse(path):
    b = open(path, "rb").read()
    if b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
    h = b.decode("utf-8", errors="replace")
    out = []
    for r in re.findall(r'<tr class="(?:odd|even)[^"]*">(.*?)</tr>', h, re.S):
        c = {k: html.unescape(re.sub(r"<[^>]+>", "", v)).strip() for k, v in re.findall(r'headers="(\w+)">(.*?)</td>', r, re.S)}
        if "Datum" not in c: continue
        try: d = dt.datetime.strptime(c["Datum"], "%d.%m.%Y").date()
        except ValueError: continue
        out.append(dict(d=d, von=c.get("Von", ""), bis=c.get("Bis", ""), thema=re.sub(r"\s+", " ", c.get("Thema", "")),
                        plz=c.get("PLZ", "").strip(), ort=re.sub(r"\s+", " ", c.get("Versammlungsort", "")), route=re.sub(r"\s+", " ", c.get("Aufzugsstrecke", ""))))
    return out

# --- Snapshots: aktueller Abruf + Wayback --------------------------------------------------------
snaps = []
for f in sorted(glob.glob(os.path.join(S, "raw/wayback/*.html"))):
    t = os.path.basename(f)[:-5]
    snaps.append(dict(ts=t, date=dt.date(int(t[:4]), int(t[4:6]), int(t[6:8])), rows=parse(f),
                      url=f"https://web.archive.org/web/{t}/{WB_URL}", abgerufen=f"{t[:4]}-{t[4:6]}-{t[6:8]}T{t[8:10]}:{t[10:12]}Z", kind="archiv"))
cur = parse(os.path.join(S, "raw/berlin.html"))
snaps = [s for s in snaps if s["rows"]]
snaps.append(dict(ts="current", date=TODAY, rows=cur, url=LIST_URL, abgerufen="2026-10-17T20:03Z", kind="aktuell"))
snaps.sort(key=lambda s: s["date"])

# Fuer jeden Tag D die Zeilen aus dem juengsten Snapshot mit Datum <= D
rows = []
for i, s in enumerate(snaps):
    nxt = snaps[i + 1]["date"] if i + 1 < len(snaps) else dt.date(2100, 1, 1)
    for r in s["rows"]:
        if s["date"] <= r["d"] < nxt or (s["kind"] == "aktuell" and r["d"] >= s["date"]):
            if START <= r["d"] <= HORIZON:
                rows.append(dict(r, src=s))
gaps = []  # Tage ohne Snapshot-Abdeckung (Snapshot liegt zu weit vorher)
day = START
while day < TODAY:
    prev = [s for s in snaps if s["date"] <= day]
    if not prev or (day - prev[-1]["date"]).days > 7: gaps.append(day.isoformat())
    day += dt.timedelta(days=1)

# --- Normalisierung ------------------------------------------------------------------------------
REC = re.compile(r"\s*\((?:vom|am|ab|jeweils)[^()]*\)\s*$")
def clean_title(t):
    t = REC.sub("", t).strip().strip(",").strip()
    t = re.sub(r"^(Thema:\s*)", "", t, flags=re.I)
    t = t.lstrip(",;'\"„“ ").strip()
    return t or "Ohne Thema"

CATS = ["Arbeit", "Klima", "Frieden und Außenpolitik", "Migration", "Wohnen", "Verkehr", "Bildung", "Gesundheit", "Landwirtschaft", "Sonstiges"]
KW = {
 "Arbeit": r"streik|tarif|lohn|löhne|gewerkschaft|ver\.?di|ig metall|beschäftigte|arbeitsplätz|arbeitnehm|arbeitsbeding|entlassung|kündigung|mindestlohn|bürgergeld|hartz|rente|sozialabbau|sozialkürz|kürzung|haushalt|betriebsrat|warnstreik|dgb|gew\b|evg|beamt|tvöd|tv-l|armut|sozialstaat|alleinerzieh|amazon",
 "Klima": r"klima|umwelt|fossil|kohle|erdgas|\bgas\b|energiewende|atomkraft|wald|bäume|baum|artenschutz|natur|letzte generation|fridays|extinction|greenpeace|biodivers|plastik|meere|emission|co2|erneuerbar",
 "Frieden und Außenpolitik": r"frieden|krieg|waffen|nato|ukrain|russland|russisch|israel|paläst|gaza|iran|syri|kurd|türkei|erdo|sudan|kongo|afghan|eritrea|tigray|armeni|aserbaid|bergkarabach|belarus|venezuela|china|tibet|uigur|hongkong|taiwan|kaschmir|pakistan|indien|bangladesch|hinrichtung|genozid|völkermord|botschaft|sanktion|rüstung|bundeswehr|wehrpflicht|militär|besatzung|libanon|jemen|irak|äthiop|nigeria|kamerun|myanmar|sri lanka|tamil|belutsch|vietnam|kuba|georgien|serbien|kosovo|bosnien|polen|ungarn|usa|trump|geisel|hamas|hisbollah|antisemit|zionis|intifada|westjordan|libyen|ägypten|marokko|westsahara|algerien|tunesien|mali|somalia|ruanda|nahost|militärdiktatur|diktatur|regime|außenpolitik|völkerrecht|un-\b|vereinte nationen|potsdamer abkommen|weltkrieg|abrüstung|drohne|kuba|cuba|kasach|pahlavi|palestin|genocid|korea|hiroshima|atombomb|ukrain|kiew|kyjiw",
 "Migration": r"migration|migrant|flucht|flüchtl|geflüchtet|asyl|abschiebung|abschiebe|refugee|rassis|einbürger|bleiberecht|aufenthalt|grenze|seenot|remigration|zuwanderung|integration",
 "Wohnen": r"miet|wohn|verdrängung|räumung|obdach|zwangsräum|enteign|sanierung|gentrifiz|bauprojekt|kiez|leerstand|hausbesetz|bebauung",
 "Verkehr": r"fahrrad|radfahr|radweg|radverkehr|verkehr|autobahn|a100|a 100|tempo ?30|critical mass|öpnv|bvg|s-bahn|u-bahn|\bbahn\b|tram|parkplatz|fußgänger|fußverkehr|kidical|autofrei|tesla|lkw|taxi|uber|mobilität|ticket|kfz|motorrad",
 "Bildung": r"schul|kita|bildung|universit|hochschul|studier|student|lehrer|lehrkräft|erzieher|ausbildung|azubi|wissenschaft|forschung|bafög|\bfu\b|\btu\b|humboldt|schüler|prüfung",
 "Gesundheit": r"gesundheit|krankenhaus|kliniken|klinik|pflege|corona|impf|medizin|hebamme|charité|vivantes|patient|cannabis|psychi|abtreibung|schwangerschaft|219a|§ ?218|aids|hiv|drogen|sucht|ärzt|krankenkasse",
 "Landwirtschaft": r"landwirt|bauern|tierhaltung|massentier|agrar|tierschutz|tierrecht|tierversuch|tiere|\btier|vegan|pelz|schlacht|fleisch|milch|ernährung|gentechnik|glyphosat|pestizid|imker|bienen",
}
KWc = {k: re.compile(v, re.I) for k, v in KW.items()}
def classify(t):
    best, score = "Sonstiges", 0
    for k in CATS[:-1]:
        n = len(KWc[k].findall(t))
        if n > score: best, score = k, n
    return best

def form(t, route):
    if route: return "Aufzug"
    if re.search(r"mahnwache|gedenk", t, re.I): return "Mahnwache"
    if re.search(r"infostand|info-stand|informationsstand", t, re.I): return "Infostand"
    return "Kundgebung"

# --- Geo -----------------------------------------------------------------------------------------
plz = {}
for line in open(os.path.join(S, "raw/plz.csv"), encoding="utf-8").read().splitlines()[1:]:
    p, la, lo = line.split(",")
    plz[p.strip()] = (float(la), float(lo))
bez = json.load(open(os.path.join(S, "raw/bezirke.json"), encoding="utf-8"))
def pip(x, y, ring):
    ins = False; j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi: ins = not ins
        j = i
    return ins
def bezirk_of(lat, lon):
    for f in bez["features"]:
        for poly in f["geometry"]["coordinates"]:
            if pip(lon, lat, poly[0]): return f["properties"]["name"]
    # naechster Bezirk (Rand-PLZ)
    best, bd = None, 1e9
    for f in bez["features"]:
        for poly in f["geometry"]["coordinates"]:
            for x, y in poly[0][::5]:
                d = (x - lon) ** 2 + (y - lat) ** 2
                if d < bd: best, bd = f["properties"]["name"], d
    return best

def jitter(key, lat, lon):
    h = hashlib.md5(key.encode()).digest()
    a = h[0] / 255 * 2 * math.pi; r = (h[1] / 255) ** 0.5 * 0.0035
    return round(lat + r * math.sin(a), 5), round(lon + r * math.cos(a) / math.cos(math.radians(lat)), 5)

def norm_place(o):
    o = re.sub(r"^\s*Neu:\s*", "", o)
    o = re.sub(r"\([^)]*\)", "", o)
    o = re.sub(r"\s+\d+[a-zA-Z]?(\s*-\s*\d+)?\s*$", "", o.strip())
    return re.sub(r"\s+", " ", o).strip().lower().replace("straße", "str.")
place_plz = collections.defaultdict(collections.Counter)
for r in rows:
    if r["plz"] and r["ort"]: place_plz[norm_place(r["ort"])][r["plz"]] += 1
for r in rows:
    if not r["ort"] and r["route"]:
        r["ort"] = re.sub(r"^\s*Neu:\s*", "", r["route"].split(" - ")[0]).strip()
        r["start_aus_route"] = True
    if not r["plz"] and r["ort"]:
        k = norm_place(r["ort"])
        if k not in place_plz and "/" in k: k = norm_place(k.split("/")[0])
        if place_plz.get(k): r["plz"] = place_plz[k].most_common(1)[0][0]; r["plz_abgeleitet"] = True

# --- Gruppierung: gleicher Termin an gleichem Ort ueber mehrere Tage = ein Ereignis -------------------
groups = collections.OrderedDict()
for r in sorted(rows, key=lambda r: (r["d"], r["von"])):
    key = (clean_title(r["thema"]).lower(), r["plz"], r["ort"].lower(), r["von"], r["bis"], r["route"].lower())
    groups.setdefault(key, []).append(r)

events = []
for key, rs in groups.items():
    r0 = rs[0]
    t = clean_title(r0["thema"])
    ll = plz.get(r0["plz"])
    if ll:
        bz = bezirk_of(*ll); lat, lon = jitter(r0["ort"].lower() + r0["plz"], *ll)
    else:
        bz, lat, lon = None, None, None
    days = sorted({r["d"] for r in rs})
    srcs = {}
    for r in rs: srcs[r["src"]["ts"]] = r["src"]
    last_src = max(srcs.values(), key=lambda s: s["date"])
    first_src = min(srcs.values(), key=lambda s: s["date"])
    plz_der = any(r.get("plz_abgeleitet") for r in rs)
    eid = f"{days[0].isoformat()}-berlin-{r0['plz'] or '00000'}-" + hashlib.sha1(repr(key).encode()).hexdigest()[:4]
    events.append(dict(
        id=eid, titel=t, thema=r0["thema"], kategorie=classify(r0["thema"]), form=form(r0["thema"], r0["route"]),
        von=r0["von"], bis=r0["bis"], tage=[d.isoformat() for d in days],
        plz=r0["plz"], plz_der=plz_der, ort=r0["ort"], bezirk=bz, lat=lat, lon=lon, route=r0["route"],
        quelle=dict(url=last_src["url"], abgerufen=last_src["abgerufen"], art=last_src["kind"]),
        zuerst=first_src["date"].isoformat(), zuletzt=last_src["date"].isoformat(),
    ))

# --- Kompakte Ausgabe: Woerterbuecher fuer Strings ---------------------------------------------------
day0 = START
def dn(s): return (dt.date.fromisoformat(s) - day0).days
def runs(ds):  # Tagesliste -> [[start,len],...]
    out = []
    for d in ds:
        if out and out[-1][0] + out[-1][1] == d: out[-1][1] += 1
        else: out.append([d, 1])
    return out
dicts = collections.defaultdict(list); idx = collections.defaultdict(dict)
def ref(name, v):
    if v not in idx[name]: idx[name][v] = len(dicts[name]); dicts[name].append(v)
    return idx[name][v]
E = []
for e in events:
    E.append([e["id"][-4:], ref("txt", e["thema"]), ref("txt", e["titel"]) if e["titel"] != e["thema"] else -1,
              CATS.index(e["kategorie"]), ref("form", e["form"]), e["von"], e["bis"], runs([dn(d) for d in e["tage"]]),
              e["plz"], ref("ort", e["ort"]), ref("bez", e["bezirk"] or "unbekannt"), e["lat"], e["lon"], ref("txt", e["route"]) if e["route"] else -1,
              1 if e["plz_der"] else 0, ref("src", (e["quelle"]["url"], e["quelle"]["abgerufen"], e["quelle"]["art"])), dn(e["zuerst"]), dn(e["zuletzt"])])

# --- Geometrien vereinfachen -----------------------------------------------------------------------
def dp(pts, eps):
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]; dmax, k = 0, 0
    for i in range(1, len(pts) - 1):
        p = pts[i]
        num = abs((b[1]-a[1])*p[0] - (b[0]-a[0])*p[1] + b[0]*a[1] - b[1]*a[0]); den = math.hypot(b[1]-a[1], b[0]-a[0]) or 1e-12
        d = num / den
        if d > dmax: dmax, k = d, i
    if dmax > eps: return dp(pts[:k+1], eps)[:-1] + dp(pts[k:], eps)
    return [a, b]
def geom(fc, namekey, eps, nd, minpts=4):
    out = []
    for f in fc["features"]:
        g = f["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = []
        for poly in polys:
            ring = poly[0]; h = len(ring) // 2  # geschlossener Ring: in zwei Haelften vereinfachen
            r = dp(ring[:h + 1], eps)[:-1] + dp(ring[h:], eps)
            if len(r) >= minpts: rings.append([[round(x, nd), round(y, nd)] for x, y in r])
        out.append(dict(n=f["properties"][namekey], id=f["properties"].get("id"), r=rings))
    return out
laender = geom(json.load(open(os.path.join(S, "raw/laender.json"), encoding="utf-8")), "name", 0.02, 3)
bezirke = geom(bez, "name", 0.0008, 4)

meta = dict(start=START.isoformat(), today=TODAY.isoformat(), horizon=HORIZON.isoformat(),
            snapshots=len(snaps) - 1, rows=len(rows), events=len(events), gaps=gaps,
            current_rows=len(cur), current_max=max(r["d"] for r in cur).isoformat(),
            snap_dates=[s["date"].isoformat() for s in snaps if s["kind"] == "archiv"])
data = dict(meta=meta, cats=CATS, dict={k: v for k, v in dicts.items()}, E=E, laender=laender, bezirke=bezirke)
out = os.path.join(S, "data/prototyp/berlin.json")
json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(json.dumps(meta | {"gaps": len(gaps), "snap_dates": len(meta["snap_dates"])}, ensure_ascii=False))
print("bytes", os.path.getsize(out))
print(collections.Counter(e["kategorie"] for e in events).most_common())
print(collections.Counter(e["form"] for e in events).most_common())
print(collections.Counter(e["bezirk"] for e in events).most_common())
