import json, sys, time, os, urllib.request, datetime as dt
out = sys.argv[1]
UA = "VersammlungsradarBot/0.1 (+https://github.com/pietvanbloom-lab/versammlungsradar)"
U = "www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege/"
cdx = f"https://web.archive.org/cdx/search/cdx?url={U}&from=20251001&to=20261016&output=json&fl=timestamp&filter=statuscode:200"
ts = [r[0] for r in json.load(urllib.request.urlopen(urllib.request.Request(cdx, headers={"User-Agent": UA})))[1:]]
# one snapshot per 4-day bucket (the earliest in the bucket), plus every snapshot before 2026-03 (sparse period)
pick, last = [], None
for t in sorted(ts):
    d = dt.date(int(t[:4]), int(t[4:6]), int(t[6:8]))
    if last is None or (d - last).days >= 4 or d < dt.date(2026, 3, 1) and (d - last).days >= 1:
        pick.append(t); last = d
print(len(pick), "snapshots", flush=True)
for t in pick:
    f = os.path.join(out, t + ".html")
    if os.path.exists(f) and os.path.getsize(f) > 10000: continue
    for attempt in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"https://web.archive.org/web/{t}id_/https://{U}", headers={"User-Agent": UA}), timeout=60)
            open(f, "wb").write(r.read()); print("ok", t, flush=True); break
        except Exception as e:
            print("retry", t, e, flush=True); time.sleep(5)
    time.sleep(1.5)
