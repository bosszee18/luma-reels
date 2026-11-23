import re
import asyncio
import statistics
from pathlib import Path

import imageio_ffmpeg

from core import FONTS_DIR

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 720, 1280, 30
MOODS = {"hangat": [220.0, 277.18, 329.63], "sinematik": [146.83, 220.0, 261.63],
         "cerah": [261.63, 329.63, 392.0], "tenang": [196.0, 246.94, 293.66]}


async def run(args: list[str], timeout: int = 1800) -> str:
    proc = await asyncio.create_subprocess_exec(FFMPEG, "-hide_banner", "-y", *args,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, err = await asyncio.wait_for(proc.communicate(), timeout)
    text = err.decode(errors="ignore")
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg gagal: " + text[-600:])
    return text


async def probe(path: str) -> dict:
    proc = await asyncio.create_subprocess_exec(FFMPEG, "-hide_banner", "-i", path,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    t = err.decode(errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", t)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    vm = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", t)
    rot = re.search(r"rotation of (-?\d+)", t) or re.search(r"rotate\s*:\s*(-?\d+)", t)
    w, h = (int(vm.group(1)), int(vm.group(2))) if vm else (0, 0)
    if rot and abs(int(rot.group(1))) in (90, 270):
        w, h = h, w
    return {"duration": dur, "width": w, "height": h, "has_video": bool(vm), "has_audio": "Audio:" in t}


async def extract_audio(src: str, out: str):
    await run(["-i", src, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", out])


async def silences(src: str, duration: float) -> list[list[float]]:
    t = await run(["-i", src, "-vn", "-af", "silencedetect=noise=-35dB:d=0.6", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", t)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", t)]
    out = []
    for i, s in enumerate(starts):
        out.append([s, ends[i] if i < len(ends) else duration])
    return out


def speech_keep(sil: list[list[float]], duration: float) -> list[list[float]]:
    keep, cur = [], 0.0
    for s, e in sil:
        if s - cur > 0.25:
            keep.append([max(0.0, cur - 0.12), min(duration, s + 0.15)])
        cur = e
    if duration - cur > 0.25:
        keep.append([max(0.0, cur - 0.12), duration])
    merged = []
    for k in keep:
        if merged and k[0] - merged[-1][1] < 0.3:
            merged[-1][1] = k[1]
        else:
            merged.append(k)
    return merged or [[0.0, duration]]


async def subject_x(src: str, start: float, end: float, work: Path) -> float:
    try:
        import cv2
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    except Exception:
        return 0.5
    xs, n = [], 6
    for i in range(n):
        t = start + (end - start) * (i + 0.5) / n
        f = work / f"probe_{i}.jpg"
        try:
            await run(["-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=480:-2", str(f)], 60)
        except RuntimeError:
            continue
        img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        faces = casc.detectMultiScale(img, 1.1, 5, minSize=(30, 30))
        if len(faces):
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            xs.append((x + w / 2) / img.shape[1])
    return round(statistics.median(xs), 3) if xs else 0.5


async def make_music(out: str, duration: float, mood: str = "hangat"):
    f = MOODS.get(mood, MOODS["hangat"])
    expr = "+".join(f"0.18*sin(2*PI*{fr}*t)*(0.55+0.45*sin(2*PI*{0.07 + i * 0.03}*t))" for i, fr in enumerate(f))
    expr += f"+0.08*sin(2*PI*{f[0] / 2}*t)"
    await run(["-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d={duration + 1:.2f}",
               "-af", "lowpass=f=1400,aecho=0.8:0.7:120:0.35,afade=t=in:d=2,"
                      f"afade=t=out:st={max(0, duration - 2):.2f}:d=2,volume=0.6",
               "-ac", "2", out], 300)


def remap_words(words: list[dict], keep: list[list[float]]) -> list[dict]:
    out, off = [], 0.0
    for ks, ke in keep:
        for w in words:
            if w["s"] >= ks - 0.05 and w["e"] <= ke + 0.05:
                out.append({"w": w["w"], "s": off + max(0.0, w["s"] - ks), "e": off + min(ke, w["e"]) - ks})
        off += ke - ks
    return out


def chunk_captions(words: list[dict], max_words: int = 4, max_dur: float = 1.8) -> list[dict]:
    caps, cur = [], []
    for w in words:
        if not w["w"]:
            continue
        if cur and (len(cur) >= max_words or w["e"] - cur[0]["s"] > max_dur or w["s"] - cur[-1]["e"] > 0.6):
            caps.append(cur)
            cur = []
        cur.append(w)
    if cur:
        caps.append(cur)
    return [{"start": round(c[0]["s"], 2), "end": round(max(c[-1]["e"], c[0]["s"] + 0.4), 2),
             "text": " ".join(x["w"] for x in c), "words": c} for c in caps]


def _ass_color(hexc: str, alpha: str = "00") -> str:
    h = (hexc or "#F3D9A2").lstrip("#")
    if len(h) != 6:
        h = "F3D9A2"
    return f"&H{alpha}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def _ts(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _esc(s: str) -> str:
    return (s or "").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def write_ass(path: str, captions: list[dict], brand: dict, hook: dict | None = None, cta: dict | None = None,
              kinetic: list[dict] | None = None, watermark: str = ""):
    acc = _ass_color(brand.get("accent", "#F3D9A2"))
    pri = _ass_color(brand.get("primary", "#1A1426"), "30")
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Liberation Sans,50,{acc},&H00FFFFFF,&H00140F1D,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,300,1
Style: Hook,Liberation Serif,58,{acc},&H00FFFFFF,{pri},{pri},-1,0,0,0,100,100,0,0,3,18,0,8,60,60,170,1
Style: Kin,Liberation Sans,78,&H00FFFFFF,&H00FFFFFF,&H00140F1D,&H80000000,-1,0,0,0,100,100,2,0,1,5,3,5,50,50,0,1
Style: Cta,Liberation Serif,52,&H00FFFFFF,&H00FFFFFF,{pri},{pri},-1,0,0,0,100,100,0,0,3,20,0,2,60,60,520,1
Style: Mark,Liberation Sans,24,&H60FFFFFF,&H60FFFFFF,&H80000000,&H00000000,-1,0,0,0,100,100,1,0,1,1,0,7,36,36,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for c in captions:
        if c.get("words"):
            parts = []
            for i, w in enumerate(c["words"]):
                nxt = c["words"][i + 1]["s"] if i + 1 < len(c["words"]) else c["end"]
                parts.append(f"{{\\kf{max(1, int((nxt - w['s']) * 100))}}}{_esc(w['w'])}")
            txt = " ".join(parts)
        else:
            txt = _esc(c["text"])
        lines.append(f"Dialogue: 1,{_ts(c['start'])},{_ts(c['end'])},Cap,,0,0,0,,{{\\fad(80,60)}}{txt}")
    if hook and hook.get("text"):
        lines.append(f"Dialogue: 2,{_ts(0)},{_ts(hook.get('dur', 2.8))},Hook,,0,0,0,,"
                     f"{{\\fad(200,250)\\t(0,400,\\fscx104\\fscy104)}}{_esc(hook['text'])}")
    if cta and cta.get("text"):
        lines.append(f"Dialogue: 2,{_ts(cta['start'])},{_ts(cta['end'])},Cta,,0,0,0,,"
                     f"{{\\fad(250,0)\\move(360,900,360,760,0,350)}}{_esc(cta['text'])}")
    for k in kinetic or []:
        lines.append(f"Dialogue: 3,{_ts(k['at'])},{_ts(k['at'] + k.get('dur', 1.6))},Kin,,0,0,0,,"
                     f"{{\\fad(120,160)\\fscx60\\fscy60\\t(0,260,\\fscx108\\fscy108)\\t(260,420,\\fscx100\\fscy100)"
                     f"\\3c{acc}}}{_esc(k['text']).upper()}")
    if watermark:
        lines.append(f"Dialogue: 0,{_ts(0)},{_ts(36000)},Mark,,0,0,0,,{_esc(watermark)}")
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def _cover(w: int, h: int) -> str:
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"


async def render(spec: dict, out: str):
    """Compose final 9:16 MP4 from a video source (with keep ranges) or still scenes."""
    args, fc, idx = [], [], 0
    base = spec["base"]
    D = spec["duration"]
    if base["type"] == "video":
        args += ["-i", base["src"]]
        src_i = idx
        idx += 1
        keep = base["keep"]
        has_a = base.get("has_audio", True)
        for j, (s, e) in enumerate(keep):
            fc.append(f"[{src_i}:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{j}]")
            if has_a:
                fc.append(f"[{src_i}:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS[a{j}]")
        if has_a:
            fc.append("".join(f"[v{j}][a{j}]" for j in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=1[bv0][ba0]")
        else:
            fc.append("".join(f"[v{j}]" for j in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=0[bv0]")
            args += ["-f", "lavfi", "-t", f"{D:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
            fc.append(f"[{idx}:a]anull[ba0]")
            idx += 1
        sw, sh = base["width"], base["height"]
        if sw / max(sh, 1) > W / H:
            cw = int(sh * W / H) // 2 * 2
            x = int(min(max(base.get("crop_x", 0.5) * sw - cw / 2, 0), sw - cw))
            crop = f"crop={cw}:{sh // 2 * 2}:{x}:0,scale={W}:{H}"
        else:
            crop = _cover(W, H)
        grade = ",eq=contrast=1.05:saturation=1.08" if spec.get("grade") else ""
        fc.append(f"[bv0]{crop},setsar=1,fps={FPS}{grade},format=yuv420p[bv]")
        fc.append("[ba0]highpass=f=80,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100[voice]")
    else:
        scenes = base["scenes"]
        for j, sc in enumerate(scenes):
            args += ["-i", sc["image"]]
            frames = int(sc["dur"] * FPS)
            z = ("min(zoom+0.0009,1.18)" if j % 2 == 0 else "if(eq(on,0),1.18,max(zoom-0.0009,1.0))")
            fc.append(f"[{idx}:v]{_cover(1080, 1920)},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                      f":d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p,"
                      f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0, sc['dur'] - 0.35):.2f}:d=0.35[s{j}]")
            idx += 1
        fc.append("".join(f"[s{j}]" for j in range(len(scenes))) + f"concat=n={len(scenes)}:v=1:a=0[bv]")
        args += ["-i", spec["voice"]]
        fc.append(f"[{idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100,apad[voice]")
        idx += 1
    cur = "bv"
    for k, ov in enumerate(spec.get("overlays", [])):
        args += ["-i", ov["image"]]
        frames = max(1, int(ov["dur"] * FPS))
        fc.append(f"[{idx}:v]{_cover(1080, 1920)},zoompan=z='min(zoom+0.0012,1.2)':x='iw/2-(iw/zoom/2)':"
                  f"y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},format=yuva420p,"
                  f"fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={max(0, ov['dur'] - 0.3):.2f}:d=0.3:alpha=1,"
                  f"setpts=PTS-STARTPTS+{ov['at']:.2f}/TB[o{k}]")
        fc.append(f"[{cur}][o{k}]overlay=0:0:eof_action=pass[c{k}]")
        cur = f"c{k}"
        idx += 1
    if spec.get("progress_bar"):
        color = spec.get("accent", "#F3D9A2").lstrip("#")
        args += ["-f", "lavfi", "-i", f"color=c=0x{color}:s={W}x6:d={D:.2f}:r={FPS}"]
        fc.append(f"[{cur}][{idx}:v]overlay=x='-w+W*t/{D:.2f}':y=H-6:eof_action=pass[pb]")
        cur = "pb"
        idx += 1
    ass = spec["ass"].replace(":", "\\:")
    fc.append(f"[{cur}]subtitles=filename='{ass}':fontsdir='{FONTS_DIR}'[vout]")
    if spec.get("music"):
        args += ["-i", spec["music"]]
        vol = spec.get("music_vol", 0.14)
        fc.append(f"[{idx}:a]volume={vol},aresample=44100[mus]")
        fc.append("[voice]asplit=2[vm][vsc]")
        fc.append("[mus][vsc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[duck]")
        fc.append("[vm][duck]amix=inputs=2:duration=first:normalize=0[aout]")
        idx += 1
    else:
        fc.append("[voice]anull[aout]")
    args += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-t", f"{D:.2f}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    await run(args, 3600)


async def thumbnail(video: str, out: str, at: float = 1.0):
    await run(["-ss", f"{at:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4", out], 120)


async def concat_audio(parts: list[str], out: str, gap: float = 0.25):
    args, fc = [], []
    for i, p in enumerate(parts):
        args += ["-i", p]
        fc.append(f"[{i}:a]aresample=44100,apad=pad_dur={gap}[p{i}]")
    fc.append("".join(f"[p{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[a]")
    await run(args + ["-filter_complex", ";".join(fc), "-map", "[a]", "-ac", "1", "-b:a", "128k", out], 600)


def srt_text(captions: list[dict]) -> str:
    def f(t):
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"
    return "\n".join(f"{i}\n{f(c['start'])} --> {f(c['end'])}\n{c['text']}\n" for i, c in enumerate(captions, 1))
