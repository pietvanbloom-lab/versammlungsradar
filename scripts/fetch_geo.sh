#!/bin/sh
# Geodaten für Karte und Zuordnung (nicht im Repo, Lizenzen der Quellen beachten).
set -e
mkdir -p raw
curl -sf -o raw/plz.csv      "https://raw.githubusercontent.com/WZBSocialScienceCenter/plz_geocoord/master/plz_geocoord.csv"
curl -sf -o raw/laender.json "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/4_niedrig.geo.json"
curl -sf -o raw/bezirke.json "https://raw.githubusercontent.com/funkeinteraktiv/Berlin-Geodaten/master/berlin_bezirke.geojson"
