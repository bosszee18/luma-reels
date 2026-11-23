import os
import json
import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Query
from fastapi.responses import Response, StreamingResponse, RedirectResponse
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError
from starlette.middleware.cors import CORSMiddleware

from core import db, client, now_iso, new_id, save_asset, get_asset, local_path, verify_sig, public_asset, init_storage
import pipeline
import publish
from trends import get_trends
from media import srt_text

try:
    from backend.clerk_auth import clerk_router, require_user
except ModuleNotFoundError:
    from clerk_auth import clerk_router, require_user

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

INDEXES: dict[str, list[IndexModel]] = {
    "projects": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                 IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
                 IndexModel([("status", ASCENDING)], name="status")],
    "videos": [IndexModel([("id", ASCENDING)], name="id", unique=True),
               IndexModel([("project_id", ASCENDING), ("rank", ASCENDING)], name="project_rank"),
               IndexModel([("user_id", ASCENDING), ("status", ASCENDING)], name="user_status")],
    "assets": [IndexModel([("id", ASCENDING)], name="id", unique=True),
               IndexModel([("user_id", ASCENDING), ("kind", ASCENDING), ("created_at", DESCENDING)], name="user_kind")],
    "brand_kits": [IndexModel([("user_id", ASCENDING)], name="user", unique=True)],
    "channels": [IndexModel([("user_id", ASCENDING), ("platform", ASCENDING)], name="user_platform", unique=True)],
    "oauth_states": [IndexModel([("state", ASCENDING)], name="state", unique=True)],
    "publications": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                     IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
                     IndexModel([("status", ASCENDING), ("scheduled_at", ASCENDING)], name="status_sched"),
                     IndexModel([("dedupe_key", ASCENDING)], name="dedupe", unique=True,
                                partialFilterExpression={"dedupe_key": {"$type": "string"}})],
    "trends": [IndexModel([("key", ASCENDING)], name="key", unique=True)],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)


app = FastAPI()
api = APIRouter(prefix="/api")
MAX_UPLOAD = 500 * 1024 * 1024
VIDEO_EXT = {"mp4", "mov", "m4v", "webm", "mkv"}


def uid_of(user: dict) -> str:
    return user["user_id"]


def base_url(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    proto = request.headers.get("x-forwarded-proto", "https").split(",")[0]
    return f"{proto}://{host.split(',')[0].strip()}"


def video_view(v: dict, assets: dict) -> dict:
    vers = []
    for ver in v.get("versions", []):
        vers.append({**{k: ver.get(k) for k in ("n", "duration", "note", "created_at", "score", "score_reason", "suggestions")},
                     "video": public_asset(assets.get(ver["video_asset_id"])),
                     "thumb": public_asset(assets.get(ver["thumb_asset_id"])),
                     "srt": public_asset(assets.get(ver["srt_asset_id"])), "caption_count": len(ver.get("captions", []))})
    plan = {k: val for k, val in v["plan"].items() if k not in ("words",)}
    for key in ("scenes", "broll"):
        if key in plan:
            plan[key] = [{**s, "image": public_asset(assets.get(s.get("asset_id")))} for s in plan[key]]
    return {**{k: v.get(k) for k in ("id", "project_id", "mode", "rank", "title", "score", "score_reason", "suggestions",
                                     "metadata", "approved_version", "status", "created_at", "updated_at", "revision_error")},
            "pending_revision": v.get("pending_revision"), "plan": plan, "versions": vers}


async def asset_map(videos: list[dict]) -> dict:
    ids = set()
    for v in videos:
        for ver in v.get("versions", []):
            ids |= {ver["video_asset_id"], ver["thumb_asset_id"], ver["srt_asset_id"]}
        for key in ("scenes", "broll"):
            ids |= {s.get("asset_id") for s in v["plan"].get(key, []) if s.get("asset_id")}
    docs = await db.assets.find({"id": {"$in": list(ids)}}, {"_id": 0}).to_list(500)
    return {d["id"]: d for d in docs}


async def own_video(vid: str, uid: str) -> dict:
    v = await db.videos.find_one({"id": vid, "user_id": uid}, {"_id": 0})
    if not v:
        raise HTTPException(404, "Video tidak ditemukan")
    return v


# ---------- basics ----------
@api.get("/")
async def root():
    return {"app": "Luma Atelier", "ok": True}


@api.get("/me")
async def me(user: dict = Depends(require_user)):
    uid = uid_of(user)
    counts = {s: await db.projects.count_documents({"user_id": uid, "status": s})
              for s in ("queued", "processing", "review", "approved", "failed")}
    return {"user_id": uid, "brand": await pipeline.brand_of(uid), "counts": counts}


class BrandKit(BaseModel):
    name: str = ""
    primary: str = Field("#1A1426", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent: str = Field("#F3D9A2", pattern=r"^#[0-9A-Fa-f]{6}$")
    voice: Literal["hangat", "sinematik", "tenang", "energik"] = "hangat"
    music_mood: Literal["hangat", "sinematik", "cerah", "tenang"] = "hangat"
    cta: str = Field("Ikuti untuk konten berikutnya", max_length=80)
    watermark: str = Field("", max_length=40)
    tone: str = Field("hangat, cerdas, tidak menggurui", max_length=120)


@api.get("/brand-kit")
async def brand_get(user: dict = Depends(require_user)):
    return await pipeline.brand_of(uid_of(user))


@api.put("/brand-kit")
async def brand_put(body: BrandKit, user: dict = Depends(require_user)):
    await db.brand_kits.update_one({"user_id": uid_of(user)}, {"$set": {**body.model_dump(), "updated_at": now_iso()}}, upsert=True)
    return await pipeline.brand_of(uid_of(user))


# ---------- assets ----------
@api.post("/uploads")
async def upload(file: UploadFile = File(...), rights_confirmed: bool = Form(False), user: dict = Depends(require_user)):
    if not rights_confirmed:
        raise HTTPException(400, "Konfirmasi bahwa Anda memiliki hak/izin atas materi ini.")
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(400, "Format tidak didukung. Gunakan MP4, MOV, M4V, WEBM, atau MKV.")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Ukuran file maksimal 500 MB.")
    ctype = {"mp4": "video/mp4", "m4v": "video/mp4", "mov": "video/quicktime", "webm": "video/webm", "mkv": "video/x-matroska"}[ext]
    a = await save_asset(uid_of(user), None, "master", data, ext, ctype,
                         filename=file.filename, meta={"rights_confirmed": True})
    return public_asset(a)


@api.get("/assets")
async def assets(kind: Optional[str] = None, user: dict = Depends(require_user)):
    q = {"user_id": uid_of(user), "is_deleted": False}
    if kind:
        q["kind"] = kind
    docs = await db.assets.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [public_asset(d) for d in docs]


@api.delete("/assets/{aid}")
async def asset_delete(aid: str, user: dict = Depends(require_user)):
    r = await db.assets.update_one({"id": aid, "user_id": uid_of(user)}, {"$set": {"is_deleted": True}})
    if not r.matched_count:
        raise HTTPException(404, "Aset tidak ditemukan")
    return {"ok": True}


@api.get("/media/{aid}")
async def media_get(aid: str, request: Request, exp: int = Query(...), sig: str = Query(...), download: int = 0):
    if not verify_sig(aid, exp, sig):
        raise HTTPException(403, "Tautan media kedaluwarsa")
    a = await get_asset(aid)
    if not a:
        raise HTTPException(404, "Media tidak ditemukan")
    path = await local_path(a)
    size = path.stat().st_size
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{a["filename"]}"'
    rng = request.headers.get("range")
    start, end, status = 0, size - 1, 200
    if rng and rng.startswith("bytes="):
        s, _, e = rng[6:].split(",")[0].partition("-")
        if s:
            start, end = int(s), min(int(e) if e else size - 1, size - 1)
        else:
            start = max(0, size - int(e))
        if start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        status = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(end - start + 1)

    def it():
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1024 * 512, left))
                if not chunk:
                    break
                left -= len(chunk)
                yield chunk
    return StreamingResponse(it(), status_code=status, media_type=a["content_type"], headers=headers)


# ---------- trends ----------
@api.get("/trends")
async def trends(refresh: bool = False, user: dict = Depends(require_user)):
    return await get_trends(refresh)


# ---------- projects ----------
class ProjectIn(BaseModel):
    mode: Literal["autoclip", "automotion", "explainer"]
    title: str = Field("", max_length=140)
    input: dict


@api.post("/projects")
async def project_create(body: ProjectIn, user: dict = Depends(require_user)):
    uid = uid_of(user)
    inp = body.input
    if body.mode == "autoclip":
        if not inp.get("master_asset_id"):
            raise HTTPException(400, "AutoClip membutuhkan file master (unggahan atau dari penyimpanan).")
        yt = inp.get("youtube_url") or ""
        if yt and not any(h in yt for h in ("youtube.com/", "youtu.be/")):
            raise HTTPException(400, "URL YouTube tidak valid.")
    if body.mode == "automotion" and not inp.get("footage_asset_id"):
        raise HTTPException(400, "AutoMotion membutuhkan footage.")
    if body.mode == "explainer":
        if inp.get("style") not in pipeline.STYLE_PROMPTS:
            raise HTTPException(400, "Pilih gaya visual: clay, 2d, 3d, atau realistis.")
        if not (inp.get("topic") or (inp.get("idea") or {}).get("title")):
            raise HTTPException(400, "Isi topik atau pilih ide.")
    for key in ("master_asset_id", "footage_asset_id"):
        if inp.get(key):
            a = await get_asset(inp[key])
            if not a or a["user_id"] != uid:
                raise HTTPException(404, "File tidak ditemukan di penyimpanan Anda.")
    title = body.title or inp.get("topic") or (inp.get("idea") or {}).get("title") or \
        {"autoclip": "Proyek AutoClip", "automotion": "Proyek AutoMotion", "explainer": "Explainer"}[body.mode]
    p = {"id": new_id(), "user_id": uid, "mode": body.mode, "title": title[:140], "input": inp, "status": "queued",
         "stages": pipeline.initial_stages(body.mode), "progress": 0, "current_stage": None, "error": None, "data": {},
         "created_at": now_iso(), "updated_at": now_iso()}
    await db.projects.insert_one(p)
    await pipeline.enqueue("project", p["id"])
    p.pop("_id", None)
    return project_view(p)


def project_view(p: dict, videos: list | None = None) -> dict:
    d = p.get("data") or {}
    return {**{k: p.get(k) for k in ("id", "mode", "title", "status", "stages", "progress", "current_stage", "error",
                                     "created_at", "updated_at")},
            "input": {k: val for k, val in (p.get("input") or {}).items()},
            "info": {"source": d.get("source"), "youtube_ref": d.get("youtube_ref"), "count_reason": d.get("count_reason"),
                     "clip_count": d.get("clip_count"), "removed_seconds": d.get("removed_seconds"),
                     "research": d.get("research"), "transcript_words": len((d.get("transcript") or {}).get("words", []))},
            **({"videos": videos} if videos is not None else {})}


@api.get("/projects")
async def projects(mode: Optional[str] = None, user: dict = Depends(require_user)):
    q = {"user_id": uid_of(user), "deleted": {"$ne": True}}
    if mode:
        q["mode"] = mode
    ps = await db.projects.find(q, {"_id": 0, "data.transcript": 0}).sort("created_at", -1).to_list(100)
    ids = [p["id"] for p in ps]
    vids = await db.videos.find({"project_id": {"$in": ids}}, {"_id": 0, "plan.words": 0}).to_list(500)
    amap = await asset_map(vids)
    by = {}
    for v in vids:
        by.setdefault(v["project_id"], []).append(v)
    out = []
    for p in ps:
        vs = sorted(by.get(p["id"], []), key=lambda x: x["rank"])
        thumb = next((public_asset(amap.get(v["versions"][-1]["thumb_asset_id"])) for v in vs if v.get("versions")), None)
        out.append({**project_view(p), "video_count": len(vs), "thumb": thumb,
                    "best_score": max([v.get("score") or 0 for v in vs], default=None),
                    "approved": sum(1 for v in vs if v.get("approved_version"))})
    return out


@api.get("/projects/{pid}")
async def project_get(pid: str, user: dict = Depends(require_user)):
    p = await db.projects.find_one({"id": pid, "user_id": uid_of(user), "deleted": {"$ne": True}}, {"_id": 0, "data.transcript": 0})
    if not p:
        raise HTTPException(404, "Proyek tidak ditemukan")
    vids = await db.videos.find({"project_id": pid}, {"_id": 0, "plan.words": 0}).sort("score", -1).to_list(20)
    amap = await asset_map(vids)
    return project_view(p, [video_view(v, amap) for v in vids])


@api.post("/projects/{pid}/retry")
async def project_retry(pid: str, user: dict = Depends(require_user)):
    p = await db.projects.find_one({"id": pid, "user_id": uid_of(user)}, {"_id": 0, "stages": 1, "status": 1})
    if not p or p["status"] != "failed":
        raise HTTPException(400, "Hanya proyek gagal yang bisa diulang")
    for s in p["stages"]:
        if s["status"] == "failed":
            s.update(status="pending", progress=0, message="")
    await db.projects.update_one({"id": pid}, {"$set": {"status": "queued", "error": None, "stages": p["stages"]}})
    await pipeline.enqueue("project", pid)
    return {"ok": True}


@api.delete("/projects/{pid}")
async def project_delete(pid: str, user: dict = Depends(require_user)):
    r = await db.projects.update_one({"id": pid, "user_id": uid_of(user)}, {"$set": {"deleted": True}})
    if not r.matched_count:
        raise HTTPException(404, "Proyek tidak ditemukan")
    return {"ok": True}


# ---------- videos / review ----------
@api.get("/review-queue")
async def review_queue(user: dict = Depends(require_user)):
    uid = uid_of(user)
    live = [p["id"] for p in await db.projects.find({"user_id": uid, "deleted": {"$ne": True}}, {"id": 1}).to_list(500)]
    vids = await db.videos.find({"user_id": uid, "project_id": {"$in": live}, "status": {"$in": ["review", "revising"]},
                                 "approved_version": None}, {"_id": 0, "plan.words": 0}).sort("updated_at", -1).to_list(30)
    vids = [v for v in vids if v.get("versions")]
    amap = await asset_map(vids)
    return [video_view(v, amap) for v in vids]


@api.get("/videos/{vid}")
async def video_get(vid: str, user: dict = Depends(require_user)):
    v = await own_video(vid, uid_of(user))
    return video_view(v, await asset_map([v]))


class ReviseIn(BaseModel):
    instruction: str = Field(..., min_length=3, max_length=600)
    target: str = Field("", max_length=80)
    start: Optional[float] = None
    end: Optional[float] = None


@api.post("/videos/{vid}/revise")
async def video_revise(vid: str, body: ReviseIn, user: dict = Depends(require_user)):
    v = await own_video(vid, uid_of(user))
    if v["status"] == "revising":
        raise HTTPException(409, "Revisi sebelumnya masih diproses")
    if not v.get("versions"):
        raise HTTPException(400, "Video belum selesai dirender")
    await db.videos.update_one({"id": vid}, {"$set": {"status": "revising", "revision_error": None,
                                                      "pending_revision": {**body.model_dump(), "requested_at": now_iso()}}})
    await pipeline.enqueue("revision", vid)
    return {"ok": True}


class ApproveIn(BaseModel):
    version: int


@api.post("/videos/{vid}/approve")
async def video_approve(vid: str, body: ApproveIn, user: dict = Depends(require_user)):
    v = await own_video(vid, uid_of(user))
    if not any(x["n"] == body.version for x in v.get("versions", [])):
        raise HTTPException(404, "Versi tidak ditemukan")
    await db.videos.update_one({"id": vid}, {"$set": {"approved_version": body.version, "status": "approved",
                                                      "approved_at": now_iso()}})
    left = await db.videos.count_documents({"project_id": v["project_id"], "approved_version": None})
    if left == 0:
        await db.projects.update_one({"id": v["project_id"]}, {"$set": {"status": "approved"}})
    return {"ok": True}


@api.post("/videos/{vid}/unapprove")
async def video_unapprove(vid: str, user: dict = Depends(require_user)):
    v = await own_video(vid, uid_of(user))
    await db.videos.update_one({"id": vid}, {"$set": {"approved_version": None, "status": "review"}})
    await db.projects.update_one({"id": v["project_id"], "status": "approved"}, {"$set": {"status": "review"}})
    return {"ok": True}


@api.get("/videos/{vid}/export/{kind}")
async def video_export(vid: str, kind: Literal["srt", "metadata"], version: Optional[int] = None,
                       user: dict = Depends(require_user)):
    v = await own_video(vid, uid_of(user))
    if not v.get("versions"):
        raise HTTPException(400, "Belum ada versi")
    ver = next((x for x in v["versions"] if x["n"] == (version or v.get("approved_version") or v["versions"][-1]["n"])), None)
    if not ver:
        raise HTTPException(404, "Versi tidak ditemukan")
    name = f"luma-{v['id'][:8]}-v{ver['n']}"
    if kind == "srt":
        return Response(srt_text(ver["captions"]), media_type="application/x-subrip",
                        headers={"Content-Disposition": f'attachment; filename="{name}.srt"'})
    meta = {"title": v["title"], "mode": v["mode"], "version": ver["n"], "approved": v.get("approved_version") == ver["n"],
            "duration_sec": ver["duration"], "editorial_score": ver.get("score"), "score_reason": ver.get("score_reason"),
            "suggestions": ver.get("suggestions"), "platforms": v.get("metadata"),
            "plan": {k: val for k, val in v["plan"].items() if k in ("hook", "cta", "context", "payoff", "start", "end", "style", "topic")},
            "exported_at": now_iso()}
    return Response(json.dumps(meta, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}-metadata.json"'})


class MetaIn(BaseModel):
    metadata: dict


@api.put("/videos/{vid}/metadata")
async def video_meta(vid: str, body: MetaIn, user: dict = Depends(require_user)):
    await own_video(vid, uid_of(user))
    clean = {p: {"title": str(m.get("title", ""))[:200], "caption": str(m.get("caption", ""))[:2200],
                 "hashtags": [str(h)[:60] for h in (m.get("hashtags") or [])][:30]}
             for p, m in body.metadata.items() if p in publish.PLATFORMS and isinstance(m, dict)}
    await db.videos.update_one({"id": vid}, {"$set": {"metadata": clean}})
    return {"ok": True}


# ---------- channels & publishing ----------
@api.get("/channels")
async def channels(user: dict = Depends(require_user)):
    return await publish.channel_list(uid_of(user))


@api.post("/channels/{platform}/connect")
async def channel_connect(platform: str, request: Request, user: dict = Depends(require_user)):
    if platform not in publish.PLATFORMS:
        raise HTTPException(404, "Kanal tidak dikenal")
    if not publish.configured(platform):
        raise HTTPException(412, {"message": "Kebutuhan konfigurasi: kredensial aplikasi resmi belum tersedia di server.",
                                  "required_env": publish.PLATFORMS[platform]["env"],
                                  "approval": publish.PLATFORMS[platform]["approval"]})
    return {"authorize_url": await publish.authorize_url(uid_of(user), platform, base_url(request))}


@api.get("/oauth/{platform}/callback")
async def oauth_cb(platform: str, request: Request, code: str = "", state: str = "", error: str = ""):
    base = base_url(request)
    if error or not code:
        return RedirectResponse(f"{base}/publikasi?oauth_error={error or 'dibatalkan'}")
    try:
        await publish.oauth_callback(platform, code, state, base)
    except Exception as e:
        logger.warning("oauth %s failed: %s", platform, e)
        return RedirectResponse(f"{base}/publikasi?oauth_error=gagal")
    return RedirectResponse(f"{base}/publikasi?connected={platform}")


@api.delete("/channels/{platform}")
async def channel_disconnect(platform: str, user: dict = Depends(require_user)):
    await db.channels.update_one({"user_id": uid_of(user), "platform": platform},
                                 {"$set": {"connected": False, "tokens": None}})
    return {"ok": True}


class PublishIn(BaseModel):
    video_id: str
    version: int
    platform: Literal["instagram", "facebook", "youtube", "tiktok"]
    visibility: Literal["public", "unlisted", "private"]
    scheduled_at: Optional[datetime] = None
    confirm: bool = False


@api.post("/publications")
async def publication_create(body: PublishIn, request: Request, user: dict = Depends(require_user)):
    uid = uid_of(user)
    v = await own_video(body.video_id, uid)
    if not body.confirm:
        raise HTTPException(400, "Konfirmasi versi, akun, visibilitas, dan waktu tayang terlebih dahulu.")
    if v.get("approved_version") != body.version or v.get("status") == "revising":
        raise HTTPException(400, "Hanya versi yang sudah disetujui yang dapat dipublikasikan.")
    if body.platform == "instagram" and body.visibility != "public":
        raise HTTPException(400, "Instagram Reels via API selalu publik; pilih Publik atau gunakan ekspor manual.")
    ch = next(c for c in await publish.channel_list(uid) if c["platform"] == body.platform)
    if not ch["configured"] or not ch["connected"]:
        raise HTTPException(412, "Akun kanal belum terhubung via OAuth. Gunakan ekspor manual sementara.")
    when = (body.scheduled_at or datetime.now(timezone.utc))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    pub = {"id": new_id(), "user_id": uid, "video_id": v["id"], "video_title": v["title"], "version": body.version,
           "platform": body.platform, "account_name": ch["account_name"], "visibility": body.visibility,
           "scheduled_at": when.astimezone(timezone.utc).isoformat(), "status": "terjadwal",
           "dedupe_key": f"{v['id']}:{body.platform}", "base": base_url(request), "created_at": now_iso(), "updated_at": now_iso()}
    try:
        await db.publications.insert_one(pub)
    except DuplicateKeyError:
        raise HTTPException(409, "Video ini sudah dijadwalkan/terbit di kanal tersebut (cegah unggahan ganda).")
    pub.pop("_id", None)
    return pub


@api.get("/publications")
async def publications(user: dict = Depends(require_user)):
    return await db.publications.find({"user_id": uid_of(user)}, {"_id": 0, "base": 0}).sort("created_at", -1).to_list(200)


@api.post("/publications/{pub_id}/cancel")
async def publication_cancel(pub_id: str, user: dict = Depends(require_user)):
    r = await db.publications.update_one({"id": pub_id, "user_id": uid_of(user), "status": "terjadwal"},
                                         {"$set": {"status": "dibatalkan", "dedupe_key": None, "updated_at": now_iso()}})
    if not r.modified_count:
        raise HTTPException(400, "Hanya jadwal yang belum dikirim yang dapat dibatalkan")
    return {"ok": True}


app.include_router(api)
app.include_router(clerk_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    app.state.index_task = asyncio.create_task(ensure_indexes())
    try:
        await asyncio.to_thread(init_storage)
    except Exception as e:
        logger.error("Storage init failed: %s", e)
    app.state.worker = asyncio.create_task(pipeline.worker_loop())
    app.state.scheduler = asyncio.create_task(publish.scheduler_loop())


@app.on_event("shutdown")
async def shutdown():
    for t in (app.state.index_task, app.state.worker, app.state.scheduler):
        t.cancel()
        with suppress(asyncio.CancelledError):
            await t
    client.close()
