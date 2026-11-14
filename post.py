"""Publishes posts from posts.json to Instagram when they are due.

Runs on a schedule in GitHub Actions. Needs one repo secret:
IG_TOKEN (long-lived Instagram user token). IG_USER_ID is optional;
when it is missing the account id is looked up from the token.
Media is served from this public repo via raw.githubusercontent.com.
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

TOKEN = (os.environ.get("IG_TOKEN") or "").strip()
# Instagram-login tokens (IG...) use graph.instagram.com; Facebook-login tokens (EAA...) use graph.facebook.com
FB_TOKEN = TOKEN.startswith("EAA")
API = "https://graph.facebook.com/v23.0" if FB_TOKEN else "https://graph.instagram.com/v23.0"
USER = os.environ.get("IG_USER_ID")
RAW = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{os.environ.get('GITHUB_REF_NAME', 'main')}/"
LATE_LIMIT = timedelta(hours=6)  # skip a post if the job missed it by more than this
ONLY = os.environ.get("ONLY_POST")  # manual run: post this number now, ignoring its time


def call(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params)
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data}")
    else:
        req = urllib.request.Request(url, data=data.encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} failed: {e.read().decode()}") from None


def wait_ready(container):
    for _ in range(30):  # up to ~5 minutes
        status = call("GET", container, fields="status_code,status")
        if status.get("status_code") == "FINISHED":
            return
        if status.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container} failed: {status}")
        time.sleep(10)
    raise RuntimeError(f"container {container} not ready after 5 minutes")


def publish(p):
    if p["type"] == "IMAGE":
        c = call("POST", f"{USER}/media", image_url=RAW + p["image"], caption=p["caption"])["id"]
    elif p["type"] == "CAROUSEL":
        kids = [call("POST", f"{USER}/media", image_url=RAW + img, is_carousel_item="true")["id"]
                for img in p["images"]]
        for k in kids:
            wait_ready(k)
        c = call("POST", f"{USER}/media", media_type="CAROUSEL", children=",".join(kids),
                 caption=p["caption"])["id"]
    else:
        c = call("POST", f"{USER}/media", media_type="REELS", video_url=RAW + p["video"],
                 cover_url=RAW + p["cover"], caption=p["caption"], share_to_feed="true")["id"]
    wait_ready(c)
    return call("POST", f"{USER}/media_publish", creation_id=c)["id"]


def find_user_id():
    if not FB_TOKEN:
        return call("GET", "me", fields="user_id,username")["user_id"]
    pages = call("GET", "me/accounts", fields="instagram_business_account{id,username}")["data"]
    for page in pages:
        ig = page.get("instagram_business_account")
        if ig:
            print(f"using Instagram account @{ig.get('username')}")
            return ig["id"]
    raise RuntimeError("Facebook token has no Page with a linked Instagram account")


def main():
    global USER
    posts = json.load(open("posts.json"))
    done = json.load(open("posted.json")) if os.path.exists("posted.json") else {}
    now = datetime.now(timezone.utc)
    failed = False
    for p in posts:
        if p["no"] in done:
            continue
        due = datetime.fromisoformat(p["publish_at_utc"].replace("Z", "+00:00"))
        if ONLY:
            if p["no"] != ONLY:
                continue
        elif now < due:
            continue
        elif now - due > LATE_LIMIT:
            print(f"no. {p['no']}: missed by more than {LATE_LIMIT}, skipping. Post it by hand.")
            done[p["no"]] = {"skipped": now.isoformat()}
            json.dump(done, open("posted.json", "w"), indent=2)
            continue
        if not TOKEN:
            print("IG_TOKEN secret not set yet, nothing posted.")
            break
        if not USER:
            USER = find_user_id()
        print(f"no. {p['no']}: publishing {p['type']}...")
        try:
            media_id = publish(p)
        except Exception as e:
            print(f"no. {p['no']}: FAILED: {e}")
            failed = True
            continue
        done[p["no"]] = {"media_id": media_id, "posted_at": datetime.now(timezone.utc).isoformat()}
        json.dump(done, open("posted.json", "w"), indent=2)
        print(f"no. {p['no']}: published, media id {media_id}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
