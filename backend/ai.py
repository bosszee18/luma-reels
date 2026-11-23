import json
import re
import base64
import logging

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from emergentintegrations.llm.openai import OpenAITextToSpeech, OpenAISpeechToText

from core import EMERGENT_KEY, new_id

log = logging.getLogger("luma.ai")
TEXT_MODEL = ("openai", "gpt-5.6-terra")
IMAGE_MODEL = "gemini-3.1-flash-image-preview"
VOICES = {"hangat": "coral", "sinematik": "onyx", "tenang": "sage", "energik": "nova"}

SYSTEM = ("Kamu adalah produser & editor video senior untuk kreator konten Indonesia. "
          "Selalu jawab HANYA dengan JSON valid tanpa markdown, tanpa komentar. Bahasa Indonesia yang natural.")


def _parse_json(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", t, re.S)
        if not m:
            raise
        return json.loads(m.group(1))


async def llm_json(prompt: str, system: str = SYSTEM, retries: int = 2):
    last = None
    for _ in range(retries + 1):
        try:
            chat = LlmChat(api_key=EMERGENT_KEY, session_id=new_id(), system_message=system).with_model(*TEXT_MODEL)
            resp = await chat.send_message(UserMessage(text=prompt))
            return _parse_json(resp if isinstance(resp, str) else str(resp))
        except Exception as e:  # retry on malformed JSON / transient error
            last = e
            log.warning("llm_json retry: %s", e)
    raise RuntimeError(f"AI teks gagal: {last}")


async def gen_image(prompt: str, reference_png: bytes | None = None) -> bytes:
    last = None
    for _ in range(3):
        try:
            chat = LlmChat(api_key=EMERGENT_KEY, session_id=new_id(), system_message="You are an image generator.")
            chat.with_model("gemini", IMAGE_MODEL).with_params(modalities=["image", "text"])
            files = [ImageContent(base64.b64encode(reference_png).decode())] if reference_png else None
            msg = UserMessage(text=prompt, file_contents=files) if files else UserMessage(text=prompt)
            _, images = await chat.send_message_multimodal_response(msg)
            if images:
                return base64.b64decode(images[0]["data"])
            last = "tidak ada gambar"
        except Exception as e:
            last = e
            log.warning("gen_image retry: %s", e)
    raise RuntimeError(f"Generator gambar gagal: {last}")


async def tts(text: str, voice_key: str = "hangat") -> bytes:
    voice = VOICES.get(voice_key, voice_key if voice_key in VOICES.values() else "coral")
    return await OpenAITextToSpeech(api_key=EMERGENT_KEY).generate_speech(
        text=text[:4000], model="tts-1-hd", voice=voice, response_format="mp3")


async def transcribe(audio_path: str, language: str | None = "id") -> dict:
    stt = OpenAISpeechToText(api_key=EMERGENT_KEY)
    with open(audio_path, "rb") as f:
        r = await stt.transcribe(file=f, model="whisper-1", response_format="verbose_json",
                                 language=language, timestamp_granularities=["segment", "word"])

    def g(o, k, d=None):
        return o.get(k, d) if isinstance(o, dict) else getattr(o, k, d)

    words = [{"w": g(w, "word", "").strip(), "s": float(g(w, "start", 0)), "e": float(g(w, "end", 0))}
             for w in (g(r, "words") or [])]
    segs = [{"s": float(g(s, "start", 0)), "e": float(g(s, "end", 0)), "t": g(s, "text", "").strip()}
            for s in (g(r, "segments") or [])]
    return {"text": g(r, "text", ""), "words": words, "segments": segs}
