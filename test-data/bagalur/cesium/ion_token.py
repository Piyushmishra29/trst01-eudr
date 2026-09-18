"""Point the page's public token at a new drone asset. PATCHing a token changes its string, so ion-public.js is rewritten. Usage: ion_token.py <asset id>"""
import sys, re, pathlib, requests
H = {"Authorization": "Bearer " + pathlib.Path("~/.config/cesium/ion-token").expanduser().read_text().strip()}; JTI = "5b7e5a5f-d47b-4fd6-a3ea-46b2755c588a"; aid = int(sys.argv[1])
r = requests.patch(f"https://api.cesium.com/v1/tokens/{JTI}", headers=H, json=dict(name="bagalur-map public page (read-only)", assetIds=[1, 2, aid], scopes=["assets:read", "geocode"],
    allowedUrls=["https://pi-vps-bombay-16gb.tail641fa8.ts.net/", "http://localhost:8766/"])); r.raise_for_status(); t = r.json()      # send every field: a partial PATCH returns 500, and a missing allowedUrls would drop the URL lock
p = pathlib.Path("web/ion-public.js"); s = re.sub(r'token: "[^"]+"', f'token: "{t["token"]}"', p.read_text()); p.write_text(re.sub(r"drone: \d+", f"drone: {aid}", s))
