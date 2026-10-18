"""Baut die statische Prototyp-Seite: Template + Ereignisdaten -> site/versammlungsradar.html."""
import os, sys
S = sys.argv[1] if len(sys.argv) > 1 else "."
t = open(f"{S}/prototype/template.html", encoding="utf-8").read()
d = open(f"{S}/data/prototyp/berlin.json", encoding="utf-8").read().replace("</", "<\\/")
os.makedirs(f"{S}/site", exist_ok=True)
open(f"{S}/site/versammlungsradar.html", "w", encoding="utf-8").write(t.replace("/*DATA*/", d))
