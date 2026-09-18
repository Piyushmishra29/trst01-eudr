"""Upload the drone GeoTIFF to Cesium ion as a tiled imagery asset. Token: ~/.config/cesium/ion-token (admin, never published)."""
import json, sys, time, pathlib, requests, boto3
TOKEN = pathlib.Path("~/.config/cesium/ion-token").expanduser().read_text().strip(); H = {"Authorization": f"Bearer {TOKEN}"}
src = pathlib.Path(sys.argv[1])
r = requests.post("https://api.cesium.com/v1/assets", headers=H, json=dict(name="Bagalur drone orthophoto (DJI_0995, 6 cm)", type="IMAGERY",
    description="One DJI Mini 3 Pro nadir photo at 350 m, aligned to satellite. The Drone Agency / TRST01 EUDR test site.", options=dict(sourceType="RASTER_IMAGERY"))); r.raise_for_status(); j = r.json()
aid = j["assetMetadata"]["id"]; up = j["uploadLocation"]; print("asset", aid)
s3 = boto3.client("s3", endpoint_url=up["endpoint"], aws_access_key_id=up["accessKey"], aws_secret_access_key=up["secretAccessKey"], aws_session_token=up["sessionToken"], region_name="us-east-1")
s3.upload_file(str(src), up["bucket"], up["prefix"] + src.name); print("uploaded")
oc = j["onComplete"]; requests.request(oc["method"], oc["url"], headers=H, json=oc["fields"]).raise_for_status()
while True:
    a = requests.get(f"https://api.cesium.com/v1/assets/{aid}", headers=H).json(); print(a["status"], a.get("percentComplete"), flush=True)
    if a["status"] in ("COMPLETE", "ERROR", "DATA_ERROR"): break
    time.sleep(10)
json.dump(dict(asset=aid), open("work/ion_asset.json", "w"))
