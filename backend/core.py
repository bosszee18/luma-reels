import os
import hmac
import hashlib
import time
import uuid
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger("luma")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
SIGN_SECRET = os.environ["MEDIA_SIGNING_SECRET"].encode()
APP_NAME = "luma-atelier"
FONTS_DIR = ROOT_DIR / "assets" / "fonts"
WORK_DIR = Path("/tmp/luma")
CACHE_DIR = WORK_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
WIB = timezone(timedelta(hours=7))

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
_storage_key = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def init_storage(force: bool = False) -> str:
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def _put(path: str, data: bytes, content_type: str) -> dict:
    for attempt in range(2):
        r = requests.put(f"{STORAGE_URL}/objects/{path}", data=data, timeout=600,
                         headers={"X-Storage-Key": init_storage(force=attempt > 0), "Content-Type": content_type})
        if r.status_code == 404 and attempt == 0:
            continue
        r.raise_for_status()
        return r.json()


def _get(path: str) -> bytes:
    for attempt in range(2):
        r = requests.get(f"{STORAGE_URL}/objects/{path}", timeout=600,
                         headers={"X-Storage-Key": init_storage(force=attempt > 0)})
        if r.status_code == 404 and attempt == 0:
            continue
        r.raise_for_status()
        return r.content


async def save_asset(user_id: str, project_id: str | None, kind: str, data: bytes, ext: str,
                     content_type: str, filename: str | None = None, meta: dict | None = None) -> dict:
    aid = new_id()
    path = f"{APP_NAME}/{user_id}/{kind}/{aid}.{ext}"
    res = await asyncio.to_thread(_put, path, data, content_type)
    doc = {"id": aid, "user_id": user_id, "project_id": project_id, "kind": kind,
           "storage_path": res["path"], "content_type": content_type, "size": len(data),
           "filename": filename or f"{kind}-{aid[:8]}.{ext}", "ext": ext, "meta": meta or {},
           "is_deleted": False, "created_at": now_iso()}
    await db.assets.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def local_path(asset: dict) -> Path:
    p = CACHE_DIR / asset["id"]
    if not p.exists():
        data = await asyncio.to_thread(_get, asset["storage_path"])
        p.write_bytes(data)
    return p


async def get_asset(asset_id: str) -> dict | None:
    return await db.assets.find_one({"id": asset_id, "is_deleted": False}, {"_id": 0})


def sign(asset_id: str, ttl: int = 6 * 3600) -> str:
    exp = int(time.time()) + ttl
    sig = hmac.new(SIGN_SECRET, f"{asset_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    base = os.environ.get("PUBLIC_MEDIA_BASE", "")
    return f"{base}/api/media/{asset_id}?exp={exp}&sig={sig}"


def verify_sig(asset_id: str, exp: int, sig: str) -> bool:
    if exp < time.time():
        return False
    good = hmac.new(SIGN_SECRET, f"{asset_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(good, sig)


def public_asset(a: dict | None) -> dict | None:
    if not a:
        return None
    return {"id": a["id"], "kind": a["kind"], "filename": a["filename"], "size": a["size"],
            "content_type": a["content_type"], "created_at": a["created_at"], "meta": a.get("meta", {}),
            "project_id": a.get("project_id"), "url": sign(a["id"])}
