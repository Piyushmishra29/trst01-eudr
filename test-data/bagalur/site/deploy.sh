#!/bin/bash
# Publish web/ to the Bombay server. Stamps BUILD in index.html first: every script, JSON and image the page asks for carries ?v=BUILD,
# so a browser can never pair a fresh page with a stale cached script (that mismatch froze the page on its loading screen once).
set -e; cd "$(dirname "$0")/web"
sed -i -E "s/const BUILD = \"[^\"]*\"/const BUILD = \"$(date +%y%m%d%H%M)\"/" index.html
rsync -azL --exclude 'a/index.html' --exclude 'a/tex_*.jpg' --exclude 'a/sat_*.jpg' --exclude 'a/three.module.js' --exclude 'a/OrbitControls.js' --exclude 'a/height_hd.png' ./ root@100.96.149.93:/srv/bagalur-estate/
grep -o 'const BUILD = "[^"]*"' index.html
