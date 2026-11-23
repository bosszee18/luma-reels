import os
import asyncio
import logging
import secrets as pysecrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

from core import db, now_iso, get_asset, local_path, sign

log = logging.getLogger("luma.publish")

PLATFORMS = {
    "instagram": {"label": "Instagram Reels", "env": ["META_APP_ID", "META_APP_SECRET"],
                  "auth": "https://www.facebook.com/v21.0/dialog/oauth",
                  "token": "https://graph.facebook.com/v21.0/oauth/access_token",
                  "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,business_management",
                  "approval": "Meta App Review untuk izin instagram_content_publish & akun Instagram Profesional yang tertaut ke Halaman Facebook."},
    "facebook": {"label": "Facebook Reels", "env": ["META_APP_ID", "META_APP_SECRET"],
                 "auth": "https://www.facebook.com/v21.0/dialog/oauth",
                 "token": "https://graph.facebook.com/v21.0/oauth/access_token",
                 "scope": "pages_show_list,pages_read_engagement,pages_manage_posts,publish_video",
                 "approval": "Meta App Review untuk pages_manage_posts & publish_video, serta peran admin di Halaman."},
    "youtube": {"label": "YouTube / Shorts", "env": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"],
                "auth": "https://accounts.google.com/o/oauth2/v2/auth",
                "token": "https://oauth2.googleapis.com/token",
                "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
                "approval": "Google OAuth consent screen + verifikasi scope youtube.upload (video dari proyek belum terverifikasi dikunci privat)."},
    "tiktok": {"label": "TikTok", "env": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"],
               "auth": "https://www.tiktok.com/v2/auth/authorize/",
               "token": "https://open.tiktokapis.com/v2/oauth/token/",
               "scope": "user.info.basic,video.publish",
               "approval": "Audit Content Posting API TikTok (sebelum audit, unggahan hanya bisa privat/SELF_ONLY) + verifikasi domain."},
}
ACTIVE = ["terjadwal", "mengirim", "terbit"]


def configured(platform: str) -> bool:
    return all(os.environ.get(k) for k in PLATFORMS[platform]["env"])


def redirect_uri(base: str, platform: str) -> str:
    return f"{os.environ.get('PUBLIC_APP_URL') or base}/api/oauth/{platform}/callback"


async def channel_list(uid: str) -> list[dict]:
    out = []
    for key, cfg in PLATFORMS.items():
        ch = await db.channels.find_one({"user_id": uid, "platform": key}, {"_id": 0, "tokens": 0}) or {}
        out.append({"platform": key, "label": cfg["label"], "configured": configured(key),
                    "connected": bool(ch.get("connected")), "account_name": ch.get("account_name"),
                    "connected_at": ch.get("connected_at"), "required_env": cfg["env"], "approval": cfg["approval"]})
    return out


async def authorize_url(uid: str, platform: str, base: str) -> str:
    cfg = PLATFORMS[platform]
    state = pysecrets.token_urlsafe(24)
    await db.oauth_states.insert_one({"state": state, "user_id": uid, "platform": platform, "created_at": now_iso()})
    cid = os.environ[cfg["env"][0]]
    params = {"redirect_uri": redirect_uri(base, platform), "state": state, "response_type": "code", "scope": cfg["scope"]}
    if platform == "tiktok":
        params["client_key"] = cid
    else:
        params["client_id"] = cid
    if platform == "youtube":
        params.update(access_type="offline", prompt="consent")
    return f"{cfg['auth']}?{urlencode(params)}"


def _exchange(platform: str, code: str, redirect: str) -> dict:
    cfg = PLATFORMS[platform]
    cid, sec = os.environ[cfg["env"][0]], os.environ[cfg["env"][1]]
    if platform == "youtube":
        r = requests.post(cfg["token"], data={"code": code, "client_id": cid, "client_secret": sec,
                                              "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=20)
    elif platform == "tiktok":
        r = requests.post(cfg["token"], data={"code": code, "client_key": cid, "client_secret": sec,
                                              "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=20)
    else:
        r = requests.get(cfg["token"], params={"code": code, "client_id": cid, "client_secret": sec,
                                               "redirect_uri": redirect}, timeout=20)
    r.raise_for_status()
    tok = r.json()
    name = None
    try:
        if platform == "youtube":
            me = requests.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                              headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=20).json()
            name = me["items"][0]["snippet"]["title"]
        elif platform == "tiktok":
            me = requests.get("https://open.tiktokapis.com/v2/user/info/", params={"fields": "display_name"},
                              headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=20).json()
            name = me["data"]["user"]["display_name"]
        else:
            pages = requests.get("https://graph.facebook.com/v21.0/me/accounts",
                                 params={"access_token": tok["access_token"], "fields": "id,name,access_token,instagram_business_account"},
                                 timeout=20).json().get("data", [])
            if pages:
                tok["page"] = pages[0]
                name = pages[0]["name"]
    except Exception as e:
        log.warning("account lookup failed: %s", e)
    return {"tokens": tok, "account_name": name}


async def oauth_callback(platform: str, code: str, state: str, base: str) -> str:
    st = await db.oauth_states.find_one_and_delete({"state": state, "platform": platform})
    if not st:
        raise ValueError("State OAuth tidak valid atau kedaluwarsa")
    res = await asyncio.to_thread(_exchange, platform, code, redirect_uri(base, platform))
    await db.channels.update_one({"user_id": st["user_id"], "platform": platform}, {"$set": {
        "connected": True, "tokens": res["tokens"], "account_name": res["account_name"], "connected_at": now_iso()}}, upsert=True)
    return st["user_id"]


# ---------- executors (official APIs) ----------
def _youtube(tokens, path, meta, visibility):
    cid, sec = os.environ["YOUTUBE_CLIENT_ID"], os.environ["YOUTUBE_CLIENT_SECRET"]
    if tokens.get("refresh_token"):
        t = requests.post(PLATFORMS["youtube"]["token"], data={"client_id": cid, "client_secret": sec,
                          "refresh_token": tokens["refresh_token"], "grant_type": "refresh_token"}, timeout=20).json()
        tokens["access_token"] = t.get("access_token", tokens["access_token"])
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    body = {"snippet": {"title": meta.get("title", "")[:100], "description": f"{meta.get('caption', '')}\n{' '.join(meta.get('hashtags', []))} #Shorts",
                        "categoryId": "22"}, "status": {"privacyStatus": visibility}}
    init = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                         json=body, headers={**h, "X-Upload-Content-Type": "video/mp4"}, timeout=30)
    init.raise_for_status()
    with open(path, "rb") as f:
        up = requests.put(init.headers["Location"], data=f, headers={**h, "Content-Type": "video/mp4"}, timeout=1200)
    up.raise_for_status()
    vid = up.json()["id"]
    return vid, f"https://youtube.com/shorts/{vid}"


def _instagram(tokens, url, meta, visibility):
    page = tokens.get("page") or {}
    ig = (page.get("instagram_business_account") or {}).get("id")
    if not ig:
        raise RuntimeError("Akun Instagram Profesional belum tertaut ke Halaman Facebook")
    tok = page.get("access_token") or tokens["access_token"]
    cap = f"{meta.get('caption', '')}\n{' '.join(meta.get('hashtags', []))}"
    c = requests.post(f"https://graph.facebook.com/v21.0/{ig}/media", data={"media_type": "REELS", "video_url": url,
                      "caption": cap, "access_token": tok}, timeout=30).json()
    if "id" not in c:
        raise RuntimeError(str(c)[:300])
    import time
    for _ in range(60):
        s = requests.get(f"https://graph.facebook.com/v21.0/{c['id']}", params={"fields": "status_code", "access_token": tok}, timeout=20).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError("Instagram gagal memproses video")
        time.sleep(5)
    p = requests.post(f"https://graph.facebook.com/v21.0/{ig}/media_publish", data={"creation_id": c["id"], "access_token": tok}, timeout=30).json()
    return p.get("id"), None


def _facebook(tokens, url, meta, visibility):
    page = tokens.get("page") or {}
    if not page:
        raise RuntimeError("Halaman Facebook tidak ditemukan pada akun")
    tok, pid = page["access_token"], page["id"]
    s = requests.post(f"https://graph.facebook.com/v21.0/{pid}/video_reels", data={"upload_phase": "start", "access_token": tok}, timeout=30).json()
    requests.post(f"https://rupload.facebook.com/video-upload/v21.0/{s['video_id']}",
                  headers={"Authorization": f"OAuth {tok}", "file_url": url}, timeout=120).raise_for_status()
    f = requests.post(f"https://graph.facebook.com/v21.0/{pid}/video_reels", data={
        "upload_phase": "finish", "video_id": s["video_id"], "video_state": "PUBLISHED" if visibility == "public" else "DRAFT",
        "description": f"{meta.get('caption', '')} {' '.join(meta.get('hashtags', []))}", "access_token": tok}, timeout=30).json()
    if not f.get("success"):
        raise RuntimeError(str(f)[:300])
    return s["video_id"], None


def _tiktok(tokens, url, meta, visibility):
    privacy = {"public": "PUBLIC_TO_EVERYONE", "unlisted": "MUTUAL_FOLLOW_FRIENDS", "private": "SELF_ONLY"}[visibility]
    r = requests.post("https://open.tiktokapis.com/v2/post/publish/video/init/", headers={
        "Authorization": f"Bearer {tokens['access_token']}", "Content-Type": "application/json; charset=UTF-8"}, json={
        "post_info": {"title": f"{meta.get('caption', '')} {' '.join(meta.get('hashtags', []))}"[:2200], "privacy_level": privacy},
        "source_info": {"source": "PULL_FROM_URL", "video_url": url}}, timeout=30).json()
    if r.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(str(r["error"])[:300])
    return r["data"]["publish_id"], None


async def execute(pub: dict, base: str):
    ch = await db.channels.find_one({"user_id": pub["user_id"], "platform": pub["platform"]}, {"_id": 0})
    if not ch or not ch.get("connected"):
        raise RuntimeError("Akun kanal belum terhubung")
    v = await db.videos.find_one({"id": pub["video_id"]}, {"_id": 0})
    if v.get("approved_version") != pub["version"] or v.get("status") == "revising":
        raise RuntimeError("Versi tidak lagi berstatus disetujui; publikasi dihentikan")
    ver = next(x for x in v["versions"] if x["n"] == pub["version"])
    asset = await get_asset(ver["video_asset_id"])
    meta = (v.get("metadata") or {}).get(pub["platform"], {})
    url = f"{os.environ.get('PUBLIC_APP_URL') or base}{sign(asset['id'], 24 * 3600)}"
    fn = {"youtube": _youtube, "instagram": _instagram, "facebook": _facebook, "tiktok": _tiktok}[pub["platform"]]
    arg = str(await local_path(asset)) if pub["platform"] == "youtube" else url
    ext_id, ext_url = await asyncio.to_thread(fn, ch["tokens"], arg, meta, pub["visibility"])
    await db.channels.update_one({"user_id": pub["user_id"], "platform": pub["platform"]}, {"$set": {"tokens": ch["tokens"]}})
    return ext_id, ext_url


async def scheduler_loop():
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            async for pub in db.publications.find({"status": "terjadwal", "scheduled_at": {"$lte": now}}, {"_id": 0}):
                claimed = await db.publications.find_one_and_update({"id": pub["id"], "status": "terjadwal"},
                                                                    {"$set": {"status": "mengirim", "updated_at": now_iso()}})
                if not claimed:
                    continue
                try:
                    ext_id, ext_url = await execute(pub, pub.get("base", ""))
                    await db.publications.update_one({"id": pub["id"]}, {"$set": {
                        "status": "terbit", "external_id": ext_id, "external_url": ext_url, "updated_at": now_iso()}})
                except Exception as e:
                    await db.publications.update_one({"id": pub["id"]}, {"$set": {"status": "gagal", "error": str(e)[:300],
                                                                                   "dedupe_key": None, "updated_at": now_iso()}})
        except Exception:
            log.exception("scheduler")
        await asyncio.sleep(20)
