"""Prints account and per-post stats for the Instagram account (run manually via the stats workflow)."""
import json, os, urllib.error, urllib.parse, urllib.request

TOKEN = os.environ["IG_TOKEN"].strip()
USER = os.environ.get("IG_USER_ID")
API = "https://graph.facebook.com/v23.0" if TOKEN.startswith("EAA") else "https://graph.instagram.com/v23.0"


def get(path, **params):
    params["access_token"] = TOKEN
    try:
        with urllib.request.urlopen(f"{API}/{path}?{urllib.parse.urlencode(params)}", timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": json.loads(e.read().decode()).get("error", {}).get("message")}


out = {"account": get(USER, fields="username,followers_count,follows_count,media_count")}
out["account_insights"] = get(f"{USER}/insights", metric="reach,follower_count", period="day")
media, url = [], f"{USER}/media"
page = get(url, fields="id,timestamp,media_type,media_product_type,like_count,comments_count,caption", limit=100)
while True:
    media += page.get("data", [])
    nxt = page.get("paging", {}).get("next")
    if not nxt or "error" in page:
        break
    with urllib.request.urlopen(nxt, timeout=60) as r:
        page = json.load(r)
for m in media:
    m["caption"] = (m.get("caption") or "").split("\n")[0][:60]
    metrics = "reach,saved,shares,views,total_interactions"
    ins = get(f"{m['id']}/insights", metric=metrics)
    m["insights"] = {d["name"]: d["values"][0]["value"] for d in ins.get("data", [])} if "data" in ins else ins
out["media"] = media
print("STATS_JSON_START")
print(json.dumps(out))
print("STATS_JSON_END")
