import json
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

import requests
import asyncio

from core import db, WIB, now_iso
from ai import llm_json

FEEDS = {"Indonesia": "https://trends.google.com/trending/rss?geo=ID",
         "Global": "https://trends.google.com/trending/rss?geo=US"}
NS = {"ht": "https://trends.google.com/trending/rss"}


def _fetch(region: str, url: str) -> list[dict]:
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 LumaAtelier"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter("item"):
        news = it.find("ht:news_item", NS)
        pub = it.findtext("pubDate")
        try:
            wib = parsedate_to_datetime(pub).astimezone(WIB).strftime("%d %b %Y, %H:%M WIB")
        except Exception:
            wib = datetime.now(WIB).strftime("%d %b %Y, %H:%M WIB")
        out.append({"term": it.findtext("title"), "traffic": it.findtext("ht:approx_traffic", "", NS), "region": region,
                    "updated_wib": wib,
                    "news_title": news.findtext("ht:news_item_title", "", NS) if news is not None else "",
                    "news_url": news.findtext("ht:news_item_url", "", NS) if news is not None else "",
                    "news_source": news.findtext("ht:news_item_source", "", NS) if news is not None else ""})
    return out[:12]


async def get_trends(refresh: bool = False) -> dict:
    cached = await db.trends.find_one({"key": "latest"}, {"_id": 0})
    if cached and not refresh:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"])
        if age < timedelta(minutes=60):
            return cached
    signals = []
    for region, url in FEEDS.items():
        try:
            signals += await asyncio.to_thread(_fetch, region, url)
        except Exception:
            pass
    fetched_wib = datetime.now(WIB).strftime("%d %b %Y, %H:%M WIB")
    if signals:
        prompt = (
            "Berikut sinyal tren pencarian aktual (Google Trends) Indonesia & Global:\n"
            + json.dumps(signals, ensure_ascii=False)
            + "\n\nPilih hingga 5 sinyal yang paling layak dijadikan video explainer edukatif 45-60 detik untuk kreator "
              "Indonesia. Hindari kriminalitas sensitif, SARA, gosip pribadi, atau korban. Usahakan campuran Indonesia & Global. "
              "Jawab JSON: {\"ideas\":[{\"signal_index\":<indeks di daftar>,\"title\":\"judul explainer\",\"angle\":\"sudut "
              "cerita 1 kalimat\",\"reason\":\"alasan relevansi untuk penonton Indonesia\",\"score\":0-100}],\"best\":<indeks ide terbaik>}")
        res = await llm_json(prompt)
        ideas = []
        for i in res.get("ideas", [])[:5]:
            idx = i.get("signal_index", 0)
            s = signals[idx] if isinstance(idx, int) and 0 <= idx < len(signals) else signals[0]
            ideas.append({"title": i.get("title"), "angle": i.get("angle"), "reason": i.get("reason"),
                          "score": i.get("score", 70), "trend_term": s["term"], "traffic": s["traffic"],
                          "region": s["region"], "updated_wib": s["updated_wib"],
                          "source": s["news_source"] or "Google Trends", "source_url": s["news_url"] or FEEDS[s["region"]],
                          "evergreen": False})
        best = res.get("best", 0) if isinstance(res.get("best"), int) else 0
    else:
        res = await llm_json(
            "Data tren tidak tersedia. Buat 5 ide explainer EVERGREEN (relevan sepanjang waktu) untuk penonton Indonesia. "
            "JSON: {\"ideas\":[{\"title\":\"\",\"angle\":\"\",\"reason\":\"\",\"score\":0-100,\"region\":\"Indonesia|Global\"}],\"best\":0}")
        ideas = [{**i, "trend_term": None, "traffic": None, "updated_wib": fetched_wib, "source": "Evergreen (tanpa data tren)",
                  "source_url": None, "evergreen": True} for i in res.get("ideas", [])[:5]]
        best = 0
    for n, idea in enumerate(ideas):
        idea["recommended"] = n == min(best, len(ideas) - 1)
    doc = {"key": "latest", "fetched_at": now_iso(), "fetched_wib": fetched_wib, "ideas": ideas,
           "live": bool(signals)}
    await db.trends.update_one({"key": "latest"}, {"$set": doc}, upsert=True)
    return doc
