#!/bin/sh
# Aktuelle Versammlungsliste der Polizei Berlin abrufen (robots.txt erlaubt den Pfad; Bot muss sich ausweisen).
set -e
mkdir -p raw
curl -sf -A "VersammlungsradarBot/0.1 (+https://github.com/pietvanbloom-lab/versammlungsradar)" \
  -o raw/berlin.html "https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege/index.php"
