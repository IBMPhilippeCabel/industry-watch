#!/usr/bin/env python3
"""Fetch RSS feeds, classify articles and write data/YYYY/MM/DD.json on main."""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.json"
MAX_PER_SOURCE = 15

SOURCES = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))

KEYWORDS = {
    "🤝 M&A": [
        "acqui", "merger", "buys", "buyout", "divest", "takeover", "stake",
        "investment", "invests", "funding", "ipo", "joint venture", "acquire",
    ],
    "⚖️ Regulation": [
        "regulat", "fda", "aafco", "fediaf", "legislation", "compliance", "labeling",
        "labelling", "recall", "safety", "standard", "ban ", "law", "policy", "eu ",
    ],
    "💡 Innovation": [
        "innovat", "launch", "new product", "novel", "technology", "ingredient",
        "research", "study", "ai ", "automation", "insect", "sustainab", "formul",
        "supplement", "unveil", "introduc",
    ],
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (petfood-watch bot)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def strip_tags(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def parse_date(value):
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def classify(text, default):
    text = text.lower()
    for category in ("🤝 M&A", "⚖️ Regulation", "💡 Innovation"):
        if any(k in text for k in KEYWORDS[category]):
            return category
    return default


def load_articles():
    articles = []
    for source in SOURCES:
        name, url, default = source["name"], source["rss"], source["default_category"]
        if not url:
            continue
        try:
            root = ET.fromstring(fetch(url))
        except Exception as exc:
            print(f"WARN {name}: {exc}", file=sys.stderr)
            continue
        items = root.findall("./channel/item")[:MAX_PER_SOURCE]
        print(f"{name}: {len(items)} articles")
        for item in items:
            title = strip_tags(item.findtext("title"))
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            summary = strip_tags(item.findtext("description"))
            tags = " ".join(c.text or "" for c in item.findall("category"))
            date = parse_date(item.findtext("pubDate"))
            articles.append({
                "source": name,
                "title": title,
                "link": link,
                "summary": summary[:220] + ("…" if len(summary) > 220 else ""),
                "date": date.isoformat() if date else None,
                "category": classify(f"{title} {summary} {tags}", default),
            })
    seen, unique = set(), []
    for a in articles:
        if a["link"] not in seen:
            seen.add(a["link"])
            unique.append(a)
    unique.sort(key=lambda a: a["date"] or "", reverse=True)
    return unique


def main():
    now = datetime.now(timezone.utc)
    out = ROOT / "data" / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    articles = load_articles()
    if not articles:
        print("ERROR: no article fetched, nothing written", file=sys.stderr)
        return 1

    out.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(articles)} articles to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
