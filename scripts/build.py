#!/usr/bin/env python3
"""Fetch RSS feeds, classify and summarize new articles, write data/YYYY/MM/DD.json on main.

Groq (free plan) is optional: without GROQ_API_KEY, or if a call fails, articles are stored
without `ai_summary` and no briefing is written. The build never fails because of Groq.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SOURCES_FILE = ROOT / "sources.json"
MAX_PER_SOURCE = 15

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"   # free plan (console.groq.com/docs/rate-limits): 30 RPM, 1K RPD, 8K TPM, 200K TPD
BATCH_SIZE = 6                      # small batches keep each call well under 8K tokens/minute
PAUSE_SECONDS = 20                  # spreads batches over the minute
BRIEFING_MAX_HEADLINES = 40

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
    return unique


# ---------------------------------------------------------------- Groq

def groq_chat(system, user, max_tokens):
    """Return the model's text, or None if no key / any failure."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    body = json.dumps({
        "model": GROQ_MODEL,
        "temperature": 0.2,
        "max_completion_tokens": max_tokens,
        "reasoning_effort": "low",      # gpt-oss: keep the hidden reasoning short
        "include_reasoning": False,     # reasoning must not end up in the answer
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(GROQ_URL, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "petfood-watch/1.0",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.load(resp)
            return (data["choices"][0]["message"].get("content") or "").strip() or None
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                wait = min(float(exc.headers.get("retry-after") or 30), 90)
                print(f"Groq rate limit, retrying in {wait:.0f}s", file=sys.stderr)
                time.sleep(wait + 1)
                continue
            print(f"WARN Groq HTTP {exc.code}: {exc.read()[:200]!r}", file=sys.stderr)
            return None
        except Exception as exc:
            print(f"WARN Groq call failed: {exc}", file=sys.stderr)
            return None
    return None


SUMMARY_SYSTEM = (
    "You write for pet food industry consultants. "
    "For each numbered article below, write a summary of exactly two short sentences in English. "
    "Use ONLY the title and description given — do not add facts, figures, names or speculation. "
    'Return ONLY a JSON object with this exact structure: {"summaries": ["two-sentence summary 1", "two-sentence summary 2", ...]} '
    "with one string entry per article, in the same order."
)


def summarize(articles):
    """Add `ai_summary` to articles (in place), batch by batch."""
    todo = [a for a in articles if not a.get("ai_summary")]
    if not todo or not os.environ.get("GROQ_API_KEY"):
        return 0
    done = 0
    batches = [todo[i:i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
    for n, batch in enumerate(batches):
        if n:
            time.sleep(PAUSE_SECONDS)
        lines = [f"{i}. {a['title']} — {a['summary']}" for i, a in enumerate(batch, 1)]
        text = groq_chat(SUMMARY_SYSTEM, "\n".join(lines), max_tokens=2500)
        try:
            payload = json.loads(text)
            summaries = payload["summaries"]
        except Exception:
            print(f"WARN batch {n + 1}/{len(batches)}: unusable Groq reply: {str(text)[:120]}", file=sys.stderr)
            continue
        if len(summaries) != len(batch):
            print(f"WARN batch {n + 1}/{len(batches)}: expected {len(batch)} summaries, got {len(summaries)}", file=sys.stderr)
            continue
        for a, s in zip(batch, summaries):
            if isinstance(s, str) and s.strip():
                a["ai_summary"] = s.strip()
                done += 1
    return done


BRIEFING_SYSTEM = (
    "You write a daily briefing for pet food industry consultants, in English, 4 to 6 sentences, "
    "grouping the headlines by theme. Use ONLY the headlines given: do not add facts, figures, "
    "names or speculation. Plain text, no bullet points, no title. "
    'Return ONLY a JSON object: {"briefing": "your text here"}'
)


def briefing(articles):
    headlines = [f"- [{a['category']}] {a['title']} ({a['source']})" for a in articles[:BRIEFING_MAX_HEADLINES]]
    text = groq_chat(BRIEFING_SYSTEM, "\n".join(headlines), max_tokens=2000)
    try:
        return json.loads(text)["briefing"]
    except Exception:
        print(f"WARN briefing parse failed: {str(text)[:120]}", file=sys.stderr)
        return None


# ---------------------------------------------------------------- main

def read_day(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def main():
    now = datetime.now(timezone.utc)
    out = DATA_DIR / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}.json"
    briefing_file = out.with_name(f"{now:%d}.briefing.txt")

    fetched = load_articles()
    if not fetched:
        print("ERROR: no article fetched, nothing written", file=sys.stderr)
        return 1

    # Articles already stored on previous days are not stored again.
    prior = {a["link"] for f in DATA_DIR.glob("*/*/*.json") if f != out for a in read_day(f)}
    previous_today = {a["link"]: a for a in read_day(out)}
    new = [a for a in fetched if a["link"] not in prior]
    # Re-run on the same day: keep earlier results (and their summaries).
    for a in new:
        if previous_today.get(a["link"], {}).get("ai_summary"):
            a["ai_summary"] = previous_today[a["link"]]["ai_summary"]
    fetched_links = {a["link"] for a in new}
    new += [a for link, a in previous_today.items() if link not in fetched_links and link not in prior]
    new.sort(key=lambda a: a["date"] or "", reverse=True)

    if not new:
        print("No new article since previous days, nothing written")
        return 0

    n_sum = summarize(new)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(new)} new articles to {out.relative_to(ROOT)} ({n_sum} summarized by Groq)")

    text = briefing(new) if os.environ.get("GROQ_API_KEY") else None
    if text:
        briefing_file.write_text(text, encoding="utf-8")
        print(f"Wrote {briefing_file.relative_to(ROOT)}")
    elif os.environ.get("GROQ_API_KEY"):
        print("WARN no briefing generated", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
