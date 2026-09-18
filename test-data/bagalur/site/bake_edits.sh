#!/usr/bin/env bash
# bake_edits.sh [parcels.json]  - bake boundaries from the page editor into the site and deploy it.
# With no argument it takes the copy saved on the server. Rebuilds images (the dimming outside the parcels follows the lines), planting, then rsyncs to Bombay.
set -e; cd "$(dirname "$0")"
if [ -n "$1" ]; then cp "$1" "work/parcels_edit_$(date +%F_%H%M%S).json"; python3 pull_edits.py "$1"; else python3 pull_edits.py; fi
python3 build_site.py 2>&1 | grep -v WARN | head -1
python3 build_flora.py && python3 build_ground.py | tail -1
./deploy.sh
echo deployed
