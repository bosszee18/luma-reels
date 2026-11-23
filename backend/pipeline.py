import json
import shutil
import asyncio
import logging
from pathlib import Path

import requests

import ai
import media
from core import db, now_iso, new_id, save_asset, local_path, get_asset, WORK_DIR

log = logging.getLogger("luma.pipeline")

STAGES = {
    "autoclip": [("ingest", "Menyiapkan bahan master"), ("transcribe", "Transkrip & timestamp"),
                 ("analyze", "Analisis momen, hook & skor"), ("visuals", "B-roll AI"),
                 ("render", "Render klip 9:16"), ("package", "Metadata & paket ekspor")],
    "automotion": [("ingest", "Menyiapkan footage"), ("transcribe", "Transkrip & timestamp"),
                   ("edit", "Rapikan jeda, audio & ritme"), ("plan", "Rencana tipografi, motion & B-roll"),
                   ("visuals", "B-roll & ilustrasi AI"), ("render", "Render video final"),
                   ("package", "Metadata & paket ekspor")],
    "explainer": [("research", "Riset topik"), ("script", "Narasi & storyboard per adegan"),
                  ("visuals", "Visual adegan konsisten"), ("voice", "Voice-over"),
                  ("subtitles", "Subtitle sinkron"), ("render", "Render video"),
                  ("package", "Skor, metadata & ekspor")],
}
STYLE_PROMPTS = {
    "clay": "Claymation stop-motion style, handcrafted plasticine characters and props, soft studio lighting, tactile textures",
    "2d": "Flat 2D vector illustration, bold geometric shapes, clean lines, subtle grain",
    "3d": "Stylized 3D animated render, soft global illumination, rounded friendly forms, cinematic depth of field",
    "realistis": "Photorealistic cinematic photograph, 35mm lens, natural dramatic lighting, shallow depth of field",
}
DEFAULT_BRAND = {"name": "", "primary": "#1A1426", "accent": "#F3D9A2", "voice": "hangat", "music_mood": "hangat",
                 "cta": "Ikuti untuk konten berikutnya", "watermark": "", "tone": "hangat, cerdas, tidak menggurui"}
META_SPEC = ('"metadata":{"youtube":{"title":"","caption":"","hashtags":["#.."]},"instagram":{...},'
             '"facebook":{...},"tiktok":{...}}')
SCORE_SPEC = ('"score":0-100,"reason":"alasan skor editorial 1-2 kalimat","suggestions":[{"t":detik,"text":"saran perbaikan"}]')

QUEUE: asyncio.Queue | None = None


def initial_stages(mode: str) -> list[dict]:
    return [{"key": k, "label": label, "status": "pending", "progress": 0, "message": "", "started_at": None,
             "finished_at": None} for k, label in STAGES[mode]]


async def brand_of(uid: str) -> dict:
    b = await db.brand_kits.find_one({"user_id": uid}, {"_id": 0}) or {}
    return {**DEFAULT_BRAND, **{k: v for k, v in b.items() if v not in (None, "")}}


class Job:
    def __init__(self, p: dict):
        self.p, self.id, self.uid = p, p["id"], p["user_id"]
        self.data = p.setdefault("data", {})

    async def set_stage(self, key, status, progress=None, message=None):
        for s in self.p["stages"]:
            if s["key"] == key:
                s["status"] = status
                if progress is not None:
                    s["progress"] = round(progress, 3)
                if message is not None:
                    s["message"] = message
                if status == "running" and not s["started_at"]:
                    s["started_at"] = now_iso()
                if status == "done":
                    s["finished_at"], s["progress"] = now_iso(), 1
        st = self.p["stages"]
        overall = sum(1 if s["status"] == "done" else s["progress"] if s["status"] == "running" else 0 for s in st) / len(st)
        await db.projects.update_one({"id": self.id}, {"$set": {"stages": st, "progress": round(overall, 3),
                                                                "current_stage": key, "updated_at": now_iso()}})

    def done(self, key):
        return any(s["key"] == key and s["status"] == "done" for s in self.p["stages"])

    async def save(self, **kw):
        self.data.update(kw)
        await db.projects.update_one({"id": self.id}, {"$set": {f"data.{k}": v for k, v in kw.items()}})

    async def stage(self, key, fn):
        if self.done(key):
            return
        await self.set_stage(key, "running", 0.02)
        await fn()
        await self.set_stage(key, "done")


# ---------- shared stages ----------
async def ingest(job: Job, asset_field: str):
    asset = await get_asset(job.p["input"].get(asset_field) or "")
    if not asset or asset["user_id"] != job.uid:
        raise RuntimeError("File master tidak ditemukan. Unggah ulang file video.")
    info = await media.probe(str(await local_path(asset)))
    if not info["has_video"] or info["duration"] < 3:
        raise RuntimeError("File bukan video yang valid atau terlalu pendek (min. 3 detik).")
    ref = None
    yt = job.p["input"].get("youtube_url")
    if yt:
        try:
            r = await asyncio.to_thread(requests.get, "https://www.youtube.com/oembed",
                                        params={"url": yt, "format": "json"}, timeout=10)
            if r.ok:
                ref = {"title": r.json().get("title"), "author": r.json().get("author_name"), "url": yt}
        except requests.RequestException:
            pass
    await job.set_stage("ingest", "running", 0.9, f"Durasi {info['duration']:.0f} dtk • {info['width']}x{info['height']}")
    await job.save(source={"asset_id": asset["id"], **info}, youtube_ref=ref)


async def transcribe(job: Job):
    src = job.data["source"]
    if not src["has_audio"]:
        await job.save(transcript={"text": "", "words": [], "segments": []})
        return
    asset = await get_asset(src["asset_id"])
    work = WORK_DIR / f"t_{job.id}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        audio = work / "audio.mp3"
        await media.extract_audio(str(await local_path(asset)), str(audio))
        await job.set_stage("transcribe", "running", 0.3, "Whisper sedang mendengarkan…")
        tr = await ai.transcribe(str(audio), job.p["input"].get("language", "id"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    await job.set_stage("transcribe", "running", 0.95, f"{len(tr['words'])} kata terdeteksi")
    await job.save(transcript=tr)


async def gen_images(job: Job, items: list[dict], prompt_of, stage_key: str, reference: bytes | None = None):
    sem = asyncio.Semaphore(3)
    done = [0]

    async def one(it):
        if it.get("asset_id"):
            return
        async with sem:
            png = await ai.gen_image(prompt_of(it), reference)
            a = await save_asset(job.uid, job.id, "image", png, "png", "image/png", meta={"prompt": it.get("prompt") or it.get("visual")})
            it["asset_id"] = a["id"]
            done[0] += 1
            await job.set_stage(stage_key, "running", done[0] / max(1, len(items)), f"Gambar {done[0]}/{len(items)}")
    await asyncio.gather(*(one(i) for i in items))


async def create_video(job: Job, rank: int, title: str, plan: dict, scored: dict) -> dict:
    v = {"id": new_id(), "project_id": job.id, "user_id": job.uid, "mode": job.p["mode"], "rank": rank,
         "title": title, "plan": plan, "score": scored.get("score"), "score_reason": scored.get("reason"),
         "suggestions": scored.get("suggestions", []), "metadata": scored.get("metadata", {}),
         "versions": [], "approved_version": None, "status": "rendering", "created_at": now_iso(), "updated_at": now_iso()}
    await db.videos.insert_one(v)
    v.pop("_id", None)
    return v


async def project_videos(pid: str) -> list[dict]:
    return await db.videos.find({"project_id": pid}, {"_id": 0}).sort("rank", 1).to_list(20)


def broll_prompt(brand):
    return lambda b: (f"{b['prompt']}. Vertical 9:16 cinematic B-roll still, rich detail, color palette accents "
                      f"{brand['accent']} and {brand['primary']}. No text, no letters, no watermark.")


async def render_version(video: dict, note: str) -> dict:
    plan, uid = video["plan"], video["user_id"]
    brand = await brand_of(uid)
    work = WORK_DIR / f"r_{new_id()}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        if plan["kind"] in ("clip", "motion"):
            src = await get_asset(plan["source_asset_id"])
            keep = plan["keep"]
            D = sum(e - s for s, e in keep)
            proj = await db.projects.find_one({"id": video["project_id"]}, {"_id": 0, "data.transcript.words": 1})
            words = media.remap_words(((proj.get("data") or {}).get("transcript") or {}).get("words", []), keep)
            base = {"type": "video", "src": str(await local_path(src)), "keep": keep, "crop_x": plan.get("crop_x", 0.5),
                    "width": plan["source_width"], "height": plan["source_height"], "has_audio": plan["has_audio"]}
        else:
            scenes = []
            for sc in plan["scenes"]:
                img = await get_asset(sc["asset_id"])
                scenes.append({"image": str(await local_path(img)), "dur": sc["dur"]})
            D = sum(s["dur"] for s in scenes)
            words = plan.get("words", [])
            voice = await get_asset(plan["voice_asset_id"])
            base = {"type": "scenes", "scenes": scenes}
        captions = media.chunk_captions(words)
        overlays = []
        for b in plan.get("broll", []):
            if b.get("asset_id"):
                dur = min(b.get("dur", 2.5), max(1.0, D - 1))
                at = min(max(0.0, b.get("at", 0)), max(0.0, D - dur - 0.2))
                overlays.append({"image": str(await local_path(await get_asset(b["asset_id"]))), "at": at, "dur": dur})
        ass = work / "subs.ass"
        media.write_ass(str(ass), captions, brand, hook={"text": plan.get("hook"), "dur": 2.8},
                        cta={"text": plan.get("cta") or brand["cta"], "start": max(0, D - 3.2), "end": D},
                        kinetic=[k for k in plan.get("kinetic", []) if k.get("at", 0) < D - 3.5],
                        watermark=brand.get("watermark", ""))
        music = work / "music.wav"
        await media.make_music(str(music), D, plan.get("music_mood") or brand["music_mood"])
        out = work / "final.mp4"
        spec = {"base": base, "duration": D, "overlays": overlays, "ass": str(ass), "music": str(music),
                "music_vol": 0.10 if plan["kind"] != "explainer" else 0.16, "grade": plan["kind"] == "motion",
                "progress_bar": plan["kind"] != "clip", "accent": brand["accent"]}
        if plan["kind"] == "explainer":
            spec["voice"] = str(await local_path(voice))
        await media.render(spec, str(out))
        thumb = work / "thumb.jpg"
        await media.thumbnail(str(out), str(thumb), min(1.5, D / 2))
        n = len(video.get("versions", [])) + 1
        slug = "".join(c if c.isalnum() else "-" for c in (video["title"] or "video").lower())[:40].strip("-")
        va = await save_asset(uid, video["project_id"], "video", out.read_bytes(), "mp4", "video/mp4",
                              filename=f"{slug}-v{n}.mp4", meta={"video_id": video["id"], "version": n})
        ta = await save_asset(uid, video["project_id"], "thumb", thumb.read_bytes(), "jpg", "image/jpeg")
        caps = [{"start": c["start"], "end": c["end"], "text": c["text"]} for c in captions]
        sa = await save_asset(uid, video["project_id"], "srt", media.srt_text(caps).encode(), "srt", "application/x-subrip",
                              filename=f"{slug}-v{n}.srt")
        ver = {"n": n, "video_asset_id": va["id"], "thumb_asset_id": ta["id"], "srt_asset_id": sa["id"],
               "duration": round(D, 2), "note": note, "captions": caps, "created_at": now_iso(),
               "score": video.get("score"), "score_reason": video.get("score_reason"),
               "suggestions": video.get("suggestions", [])}
        video.setdefault("versions", []).append(ver)
        await db.videos.update_one({"id": video["id"]}, {"$push": {"versions": ver},
                                                         "$set": {"status": "review", "updated_at": now_iso()}})
        return ver
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---------- AutoClip ----------
async def run_autoclip(job: Job):
    await job.stage("ingest", lambda: ingest(job, "master_asset_id"))
    await job.stage("transcribe", lambda: transcribe(job))
    src = job.data["source"]
    brand = await brand_of(job.uid)

    async def analyze():
        tr = job.data["transcript"]
        D = src["duration"]
        target = int(job.p["input"].get("target_clips", 5))
        maxlen = int(job.p["input"].get("max_len", 60))
        lines = "\n".join(f"[{s['s']:.1f}-{s['e']:.1f}] {s['t']}" for s in tr["segments"])[:16000]
        ref = job.data.get("youtube_ref")
        if not lines.strip():
            n = max(1, min(target, int(D // 20)))
            seg = D / n
            res = {"clips": [{"start": i * seg, "end": min(D, i * seg + min(seg, maxlen)), "title": f"Momen {i + 1}",
                              "hook": "Lihat momen ini", "context": "", "payoff": "", "cta": brand["cta"],
                              "broll_prompt": "", "score": 40, "reason": "Tidak ada ucapan terdeteksi; klip dipotong rata.",
                              "suggestions": [], "metadata": {}} for i in range(n)],
                   "count_reason": "Tidak ada ucapan yang terdeteksi pada audio, jadi momen tidak dapat dianalisis dari transkrip."}
        else:
            prompt = (
                f"Durasi video master: {D:.1f} detik. Referensi YouTube: {json.dumps(ref, ensure_ascii=False)}.\n"
                f"Brand: nada {brand['tone']}; CTA default: '{brand['cta']}'.\n"
                f"Transkrip bertimestamp:\n{lines}\n\n"
                f"Pilih hingga {target} klip pendek BERBEDA (tidak tumpang tindih, topik berbeda), masing-masing 20-{maxlen} detik, "
                "mulai & berakhir di batas kalimat. Tiap klip harus punya alur hook -> konteks -> payoff -> CTA. "
                "Jangan memaksakan klip lemah; jika bahan hanya mendukung lebih sedikit, jelaskan alasannya di count_reason. "
                "Jawab JSON: {\"clips\":[{\"start\":detik,\"end\":detik,\"title\":\"judul\",\"hook\":\"teks hook di layar maks 8 kata\","
                "\"context\":\"ringkas konteks\",\"payoff\":\"ringkas payoff\",\"cta\":\"CTA sesuai isi maks 8 kata\","
                "\"broll_prompt\":\"English visual description for one B-roll cutaway supporting the context\","
                "\"broll_at\":detik relatif dari awal klip (di bagian konteks)," + SCORE_SPEC + " (t relatif terhadap klip),"
                + META_SPEC + "}],\"count_reason\":\"kosong jika jumlah klip sesuai target\"}")
            res = await llm_json_safe(prompt)
        clips, used = [], []
        for c in res.get("clips", []):
            try:
                s, e = max(0.0, float(c["start"])), min(D, float(c["end"]))
            except (KeyError, TypeError, ValueError):
                continue
            if e - s > maxlen:
                e = s + maxlen
            if e - s < 8 or any(s < ue and e > us for us, ue in used):
                continue
            used.append((s, e))
            clips.append({**c, "start": round(s, 2), "end": round(e, 2)})
        clips = clips[:target]
        if not clips:
            raise RuntimeError("Bahan tidak cukup untuk membentuk satu klip pun (butuh ucapan minimal ±8 detik).")
        reason = (res.get("count_reason") or "").strip()
        if len(clips) < target and not reason:
            reason = (f"Bahan berdurasi {D:.0f} detik hanya mendukung {len(clips)} momen kuat yang tidak tumpang tindih; "
                      "klip tambahan akan mengulang atau terlalu lemah.")
        await job.set_stage("analyze", "running", 0.7, "Mendeteksi subjek untuk crop…")
        work = WORK_DIR / f"a_{job.id}"
        work.mkdir(parents=True, exist_ok=True)
        srcp = str(await local_path(await get_asset(src["asset_id"])))
        clips.sort(key=lambda c: -(c.get("score") or 0))
        for rank, c in enumerate(clips, 1):
            cx = await media.subject_x(srcp, c["start"], c["end"], work)
            dur = c["end"] - c["start"]
            broll = []
            if c.get("broll_prompt"):
                at = float(c.get("broll_at") or dur * 0.35)
                broll = [{"prompt": c["broll_prompt"], "at": min(max(3.0, at), max(3.0, dur - 6)), "dur": 2.6}]
            plan = {"kind": "clip", "source_asset_id": src["asset_id"], "source_width": src["width"],
                    "source_height": src["height"], "has_audio": src["has_audio"], "keep": [[c["start"], c["end"]]],
                    "start": c["start"], "end": c["end"], "crop_x": cx, "hook": c.get("hook"), "context": c.get("context"),
                    "payoff": c.get("payoff"), "cta": c.get("cta") or brand["cta"], "broll": broll,
                    "music_mood": brand["music_mood"]}
            await create_video(job, rank, c.get("title") or f"Klip {rank}", plan, c)
        shutil.rmtree(work, ignore_errors=True)
        await job.save(count_reason=reason if len(clips) < target else "", clip_count=len(clips))

    await job.stage("analyze", analyze)
    videos = await project_videos(job.id)

    async def visuals():
        for v in videos:
            await gen_images(job, v["plan"]["broll"], broll_prompt(brand), "visuals")
            await db.videos.update_one({"id": v["id"]}, {"$set": {"plan.broll": v["plan"]["broll"]}})
    await job.stage("visuals", visuals)
    await render_all(job, videos)
    await job.stage("package", lambda: finish_package(job))


async def render_all(job: Job, videos: list[dict]):
    async def render():
        for i, v in enumerate(videos):
            if v.get("versions"):
                continue
            await job.set_stage("render", "running", i / len(videos), f"Render {i + 1}/{len(videos)}: {v['title']}")
            await render_version(v, "Versi awal AI")
    await job.stage("render", render)


async def finish_package(job: Job):
    await db.projects.update_one({"id": job.id}, {"$set": {"status": "review", "updated_at": now_iso()}})


async def llm_json_safe(prompt: str) -> dict:
    res = await ai.llm_json(prompt)
    return res if isinstance(res, dict) else {}


# ---------- AutoMotion ----------
async def run_automotion(job: Job):
    await job.stage("ingest", lambda: ingest(job, "footage_asset_id"))
    await job.stage("transcribe", lambda: transcribe(job))
    src = job.data["source"]
    brand = await brand_of(job.uid)

    async def edit():
        srcp = str(await local_path(await get_asset(src["asset_id"])))
        keep = [[0.0, src["duration"]]]
        if src["has_audio"]:
            keep = media.speech_keep(await media.silences(srcp, src["duration"]), src["duration"])
        kept = sum(e - s for s, e in keep)
        work = WORK_DIR / f"e_{job.id}"
        work.mkdir(parents=True, exist_ok=True)
        cx = await media.subject_x(srcp, 0, src["duration"], work)
        shutil.rmtree(work, ignore_errors=True)
        await job.save(keep=keep, crop_x=cx, removed_seconds=round(src["duration"] - kept, 1))
        await job.set_stage("edit", "running", 0.95, f"{src['duration'] - kept:.1f} dtk jeda dipangkas • {len(keep)} potongan")

    await job.stage("edit", edit)

    async def plan():
        keep = job.data["keep"]
        D = sum(e - s for s, e in keep)
        caps = media.chunk_captions(media.remap_words(job.data["transcript"]["words"], keep), 8, 4)
        lines = "\n".join(f"[{c['start']:.1f}-{c['end']:.1f}] {c['text']}" for c in caps)[:14000]
        intent = job.p["input"].get("intent") or ""
        prompt = (
            f"Footage telah dirapikan menjadi {D:.1f} detik. Tujuan kreator: '{intent}'. Nada brand: {brand['tone']}.\n"
            f"Transkrip (timeline hasil edit):\n{lines or '(tanpa ucapan)'}\n\n"
            "Rancang paket motion: judul, hook di layar, 3-6 tipografi kinetik (frasa kunci 1-3 kata tepat saat diucapkan), "
            "2-3 sisipan B-roll/ilustrasi kontekstual (hindari 3 detik pertama dan 4 detik terakhir), CTA. "
            "Jawab JSON: {\"title\":\"\",\"hook\":\"maks 8 kata\",\"kinetic\":[{\"at\":detik,\"dur\":1.6,\"text\":\"\"}],"
            "\"broll\":[{\"at\":detik,\"dur\":2.5,\"type\":\"broll|ilustrasi\",\"prompt\":\"English visual description\"}],"
            "\"cta\":\"maks 8 kata\"," + SCORE_SPEC + "," + META_SPEC + "}")
        res = await llm_json_safe(prompt)
        broll = [{"prompt": b.get("prompt", ""), "at": float(b.get("at", 4)), "dur": float(b.get("dur", 2.5)),
                  "type": b.get("type", "broll")} for b in res.get("broll", [])[:3] if b.get("prompt")]
        p = {"kind": "motion", "source_asset_id": src["asset_id"], "source_width": src["width"],
             "source_height": src["height"], "has_audio": src["has_audio"], "keep": keep,
             "crop_x": job.data.get("crop_x", 0.5), "hook": res.get("hook"), "cta": res.get("cta") or brand["cta"],
             "kinetic": res.get("kinetic", [])[:6], "broll": broll, "music_mood": brand["music_mood"],
             "removed_seconds": job.data.get("removed_seconds")}
        await create_video(job, 1, res.get("title") or job.p["title"], p, res)

    await job.stage("plan", plan)
    videos = await project_videos(job.id)

    async def visuals():
        v = videos[0]
        await gen_images(job, v["plan"]["broll"], broll_prompt(brand), "visuals")
        await db.videos.update_one({"id": v["id"]}, {"$set": {"plan.broll": v["plan"]["broll"]}})
    await job.stage("visuals", visuals)
    await render_all(job, videos)
    await job.stage("package", lambda: finish_package(job))


# ---------- Explainer ----------
def scene_prompt(plan):
    return lambda sc: (f"{STYLE_PROMPTS.get(plan['style'], STYLE_PROMPTS['3d'])}. Vertical 9:16 composition. "
                       f"Style bible (keep identical across scenes): {plan['style_bible']}. "
                       f"Scene: {sc['visual']}. No text, no letters, no captions, no watermark.")


async def build_voice(job_uid: str, pid: str, plan: dict, voice_key: str, progress=None):
    work = WORK_DIR / f"v_{new_id()}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        for i, sc in enumerate(plan["scenes"]):
            if not sc.get("audio_asset_id"):
                mp3 = await ai.tts(sc["narration"], voice_key)
                a = await save_asset(job_uid, pid, "audio", mp3, "mp3", "audio/mpeg", meta={"scene": i})
                sc["audio_asset_id"] = a["id"]
            if progress:
                await progress(i + 1, len(plan["scenes"]))
        parts = []
        for sc in plan["scenes"]:
            p = await local_path(await get_asset(sc["audio_asset_id"]))
            sc["dur"] = round((await media.probe(str(p)))["duration"] + 0.25, 2)
            parts.append(str(p))
        track = work / "voice.mp3"
        await media.concat_audio(parts, str(track))
        va = await save_asset(job_uid, pid, "audio", track.read_bytes(), "mp3", "audio/mpeg", meta={"voice_track": True})
        plan["voice_asset_id"] = va["id"]
        tr = await ai.transcribe(str(track), "id")
        plan["words"] = align_words(plan["scenes"], tr["words"])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def align_words(scenes: list[dict], heard: list[dict]) -> list[dict]:
    """Exact narration text, timed by Whisper words inside each scene window (fallback: proportional)."""
    out, t0 = [], 0.0
    for sc in scenes:
        t1 = t0 + sc["dur"]
        words = sc["narration"].split()
        win = [w for w in heard if t0 - 0.1 <= w["s"] < t1 - 0.1]
        for j, word in enumerate(words):
            if win:
                k = min(len(win) - 1, j * len(win) // len(words))
                s = win[k]["s"]
                e = win[min(len(win) - 1, (j + 1) * len(win) // len(words))]["s"] if j + 1 < len(words) else win[-1]["e"]
            else:
                span = (sc["dur"] - 0.25) / len(words)
                s, e = t0 + j * span, t0 + (j + 1) * span
            out.append({"w": word, "s": round(s, 2), "e": round(max(e, s + 0.12), 2)})
        t0 = t1
    return out


async def run_explainer(job: Job):
    inp = job.p["input"]
    brand = await brand_of(job.uid)
    idea = inp.get("idea") or {}
    topic = inp.get("topic") or idea.get("title") or job.p["title"]

    async def research():
        res = await llm_json_safe(
            f"Topik explainer: '{topic}'. Konteks tren: {json.dumps(idea, ensure_ascii=False)}.\n"
            "Buat riset ringkas untuk video explainer 45-60 detik bagi penonton Indonesia. Bedakan fakta yang mapan dan hal "
            "yang perlu diverifikasi. JSON: {\"summary\":\"\",\"key_facts\":[\"\"],\"audience_insight\":\"\","
            "\"verify_notes\":[\"hal yang perlu dicek kreator\"],\"sources\":[\"nama sumber yang disarankan untuk verifikasi\"]}")
        await job.save(research=res, topic=topic)
    await job.stage("research", research)

    async def script():
        style = inp.get("style", "3d")
        res = await llm_json_safe(
            f"Riset: {json.dumps(job.data['research'], ensure_ascii=False)}\nTopik: {topic}. Gaya visual: {style}. "
            f"Palet brand: {brand['primary']} & {brand['accent']}. Nada: {brand['tone']}. CTA default: {brand['cta']}.\n"
            "Tulis narasi voice-over Bahasa Indonesia 110-140 kata total dibagi 5-6 adegan, dengan hook kuat di adegan 1 dan "
            "CTA di akhir. Buat style bible agar karakter, palet, dan pencahayaan konsisten antaradegan. JSON: "
            "{\"title\":\"\",\"hook\":\"teks hook di layar maks 7 kata\",\"cta\":\"maks 7 kata\",\"style_bible\":\"English: "
            "main character description (if any), palette, lighting, environment\",\"scenes\":[{\"narration\":\"\","
            "\"visual\":\"English scene description\",\"on_screen\":\"kata kunci 1-3 kata\"}]}")
        scenes = [{"narration": s["narration"], "visual": s.get("visual", topic), "on_screen": s.get("on_screen", "")}
                  for s in res.get("scenes", [])[:6] if s.get("narration")]
        if len(scenes) < 3:
            raise RuntimeError("Naskah AI tidak lengkap, silakan coba ulang.")
        plan = {"kind": "explainer", "style": style, "style_bible": res.get("style_bible", ""), "scenes": scenes,
                "hook": res.get("hook"), "cta": res.get("cta") or brand["cta"], "voice": inp.get("voice") or brand["voice"],
                "music_mood": "sinematik" if (inp.get("voice") or brand["voice"]) == "sinematik" else brand["music_mood"],
                "topic": topic, "idea": idea or None}
        await create_video(job, 1, res.get("title") or topic, plan, {})
    await job.stage("script", script)
    v = (await project_videos(job.id))[0]
    plan = v["plan"]

    async def visuals():
        first = plan["scenes"][0]
        await gen_images(job, [first], scene_prompt(plan), "visuals")
        ref = (await local_path(await get_asset(first["asset_id"]))).read_bytes()
        await gen_images(job, plan["scenes"][1:], lambda sc: "Keep the same character design, palette and art style as the "
                         "reference image. " + scene_prompt(plan)(sc), "visuals", ref)
        await db.videos.update_one({"id": v["id"]}, {"$set": {"plan.scenes": plan["scenes"]}})
    await job.stage("visuals", visuals)

    async def voice():
        async def prog(i, n):
            await job.set_stage("voice", "running", i / n * 0.8, f"Adegan {i}/{n}")
        await build_voice(job.uid, job.id, plan, plan["voice"], prog)
        await db.videos.update_one({"id": v["id"]}, {"$set": {"plan": plan}})
    await job.stage("voice", voice)

    async def subtitles():
        await job.set_stage("subtitles", "running", 0.9, f"{len(plan.get('words', []))} kata tersinkron")
    await job.stage("subtitles", subtitles)

    async def rscore():
        res = await score_video(v)
        v.update(score=res.get("score"), score_reason=res.get("reason"), suggestions=res.get("suggestions", []),
                 metadata=res.get("metadata", {}))
        await db.videos.update_one({"id": v["id"]}, {"$set": {k: v[k] for k in ("score", "score_reason", "suggestions", "metadata")}})

    async def render():
        if not v.get("score"):
            await rscore()
        if not v.get("versions"):
            await render_version(v, "Versi awal AI")
    await job.stage("render", render)
    await job.stage("package", lambda: finish_package(job))


async def score_video(v: dict, change: str = "") -> dict:
    p = v["plan"]
    if p["kind"] == "explainer":
        body = " | ".join(f"[adegan {i + 1}] {s['narration']}" for i, s in enumerate(p["scenes"]))
        t = 0.0
        times = []
        for s in p["scenes"]:
            times.append(round(t, 1))
            t += s.get("dur", 8)
        body += f"\nWaktu mulai adegan (detik): {times}"
    else:
        body = f"Hook: {p.get('hook')} | Konteks: {p.get('context')} | Payoff: {p.get('payoff')} | CTA: {p.get('cta')}"
    return await llm_json_safe(
        f"Nilai video vertikal berjudul '{v['title']}' ({p['kind']}). Hook layar: {p.get('hook')}. CTA: {p.get('cta')}.\n"
        f"{body}\nPerubahan terakhir: {change or '-'}\n"
        "Beri skor editorial jujur 0-100 (hook, kejelasan, ritme, payoff, CTA), alasan, dan 2-4 saran perbaikan dengan timestamp. "
        "Buat juga judul, caption, dan hashtag per platform. JSON: {" + SCORE_SPEC + "," + META_SPEC + "}")


# ---------- revisions ----------
EDITABLE = {"clip": ["start", "end", "hook", "cta", "broll", "music_mood"],
            "motion": ["hook", "cta", "kinetic", "broll", "music_mood"],
            "explainer": ["hook", "cta", "scenes", "music_mood", "voice"]}


async def run_revision(video_id: str):
    v = await db.videos.find_one({"id": video_id}, {"_id": 0})
    req = v.get("pending_revision")
    if not req:
        return
    plan = v["plan"]
    kind = plan["kind"]
    editable = {k: plan.get(k) for k in EDITABLE[kind]}
    if kind == "explainer":
        editable["scenes"] = [{"narration": s["narration"], "visual": s["visual"], "on_screen": s.get("on_screen", "")}
                              for s in plan["scenes"]]
    if kind != "explainer":
        editable["broll"] = [{k: b.get(k) for k in ("at", "dur", "prompt")} for b in plan.get("broll", [])]
    res = await llm_json_safe(
        f"Rencana video saat ini (JSON): {json.dumps(editable, ensure_ascii=False)}\n"
        f"Bagian yang direvisi: {req.get('target') or 'umum'} (rentang {req.get('start')}–{req.get('end')} detik jika ada).\n"
        f"Instruksi kreator: {req['instruction']}\n"
        "Ubah HANYA bagian yang diminta, pertahankan sisanya persis. Untuk klip, start/end adalah detik pada video master. "
        "music_mood salah satu: hangat, sinematik, cerah, tenang. voice: hangat, sinematik, tenang, energik. "
        "JSON: {\"plan\":{...field yang sama...},\"change_summary\":\"ringkasan perubahan\"}")
    new = res.get("plan") or {}
    summary = res.get("change_summary") or req["instruction"]
    if kind == "clip":
        try:
            s, e = float(new.get("start", plan["start"])), float(new.get("end", plan["end"]))
            proj = await db.projects.find_one({"id": v["project_id"]}, {"_id": 0, "data.source.duration": 1})
            D = proj["data"]["source"]["duration"]
            s, e = max(0.0, s), min(D, e)
            if e - s >= 5:
                plan.update(start=round(s, 2), end=round(e, 2), keep=[[round(s, 2), round(e, 2)]])
        except (TypeError, ValueError, KeyError):
            pass
    for k in ("hook", "cta", "music_mood", "kinetic"):
        if k in new and k in EDITABLE[kind] and new[k] is not None:
            plan[k] = new[k]
    if "broll" in new and kind != "explainer" and isinstance(new["broll"], list):
        old = {b["prompt"]: b.get("asset_id") for b in plan.get("broll", [])}
        plan["broll"] = [{"prompt": b["prompt"], "at": float(b.get("at", 4)), "dur": float(b.get("dur", 2.5)),
                          "asset_id": old.get(b["prompt"])} for b in new["broll"][:3] if b.get("prompt")]
    brand = await brand_of(v["user_id"])
    fake_job = Job({"id": v["project_id"], "user_id": v["user_id"], "stages": [], "data": {}})
    fake_job.set_stage = _noop
    if kind == "explainer":
        voice_changed = new.get("voice") and new["voice"] != plan.get("voice")
        if voice_changed:
            plan["voice"] = new["voice"]
        scenes = new.get("scenes") if isinstance(new.get("scenes"), list) and new.get("scenes") else None
        if scenes:
            merged = []
            for i, ns in enumerate(scenes[:6]):
                old = plan["scenes"][i] if i < len(plan["scenes"]) else {}
                sc = {"narration": ns.get("narration") or old.get("narration", ""), "visual": ns.get("visual") or old.get("visual", ""),
                      "on_screen": ns.get("on_screen", "")}
                if old and sc["visual"] == old.get("visual"):
                    sc["asset_id"] = old.get("asset_id")
                if old and sc["narration"] == old.get("narration") and not voice_changed:
                    sc["audio_asset_id"] = old.get("audio_asset_id")
                    if old.get("dur"):
                        sc["dur"] = old["dur"]
                merged.append(sc)
            plan["scenes"] = merged
        if voice_changed:
            for sc in plan["scenes"]:
                sc.pop("audio_asset_id", None)
        ref = (await local_path(await get_asset(plan["scenes"][0]["asset_id"]))).read_bytes() if plan["scenes"][0].get("asset_id") else None
        await gen_images(fake_job, plan["scenes"], scene_prompt(plan), "visuals", ref)
        if any(not sc.get("audio_asset_id") or not sc.get("dur") for sc in plan["scenes"]) or not plan.get("voice_asset_id"):
            await build_voice(v["user_id"], v["project_id"], plan, plan["voice"])
    else:
        await gen_images(fake_job, plan["broll"], broll_prompt(brand), "visuals")
    v["plan"] = plan
    await db.videos.update_one({"id": v["id"]}, {"$set": {"plan": plan}})
    sc = await score_video(v, summary)
    v.update(score=sc.get("score", v.get("score")), score_reason=sc.get("reason", v.get("score_reason")),
             suggestions=sc.get("suggestions", v.get("suggestions")), metadata=sc.get("metadata") or v.get("metadata"))
    await render_version(v, f"Revisi: {summary}")
    await db.videos.update_one({"id": v["id"]}, {"$set": {
        "score": v["score"], "score_reason": v["score_reason"], "suggestions": v["suggestions"], "metadata": v["metadata"],
        "status": "review", "pending_revision": None, "revision_error": None, "updated_at": now_iso()}})


async def _noop(*a, **k):
    return None


# ---------- worker ----------
RUNNERS = {"autoclip": run_autoclip, "automotion": run_automotion, "explainer": run_explainer}


async def run_project(pid: str):
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    if not p or p["status"] not in ("queued", "processing"):
        return
    await db.projects.update_one({"id": pid}, {"$set": {"status": "processing", "error": None}})
    p["status"] = "processing"
    job = Job(p)
    try:
        await RUNNERS[p["mode"]](job)
    except Exception as e:
        log.exception("project %s failed", pid)
        for s in job.p["stages"]:
            if s["status"] == "running":
                s["status"], s["message"] = "failed", str(e)[:300]
        await db.projects.update_one({"id": pid}, {"$set": {"status": "failed", "error": str(e)[:500],
                                                            "stages": job.p["stages"], "updated_at": now_iso()}})


async def enqueue(kind: str, ident: str):
    await QUEUE.put((kind, ident))


async def _execute(sem, kind, ident):
    async with sem:
        if kind == "project":
            await run_project(ident)
        else:
            try:
                await run_revision(ident)
            except Exception as e:
                log.exception("revision %s failed", ident)
                await db.videos.update_one({"id": ident}, {"$set": {"status": "review", "pending_revision": None,
                                                                    "revision_error": str(e)[:300]}})


async def worker_loop():
    global QUEUE
    QUEUE = asyncio.Queue()
    sem = asyncio.Semaphore(2)
    async for p in db.projects.find({"status": {"$in": ["queued", "processing"]}}, {"_id": 0, "id": 1}):
        await db.projects.update_one({"id": p["id"]}, {"$set": {"status": "queued"}})
        await QUEUE.put(("project", p["id"]))
    async for v in db.videos.find({"status": "revising"}, {"_id": 0, "id": 1}):
        await QUEUE.put(("revision", v["id"]))
    while True:
        kind, ident = await QUEUE.get()
        asyncio.create_task(_execute(sem, kind, ident))
