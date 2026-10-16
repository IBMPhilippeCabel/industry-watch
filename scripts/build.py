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
MAX_PER_SOURCE = 15

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"   # free plan (console.groq.com/docs/rate-limits): 30 RPM, 1K RPD, 8K TPM, 200K TPD
BATCH_SIZE = 6                      # small batches keep each call well under 8K tokens/minute
PAUSE_SECONDS = 20                  # spreads batches over the minute
BRIEFING_MAX_HEADLINES = 40


def _load_site_cfg(site_id=None):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    sites = cfg["sites"]
    if site_id:
        matches = [s for s in sites if s["id"] == site_id]
        if not matches:
            raise SystemExit(f"ERROR: site id {site_id!r} not found in config.json")
        return matches[0]
    return sites[0]

# Resolved from CLI arg --site <id>, or first site in config.
_site_id = None
for _i, _arg in enumerate(sys.argv[1:]):
    if _arg == "--site" and _i + 1 < len(sys.argv) - 1:
        _site_id = sys.argv[_i + 2]
        break

_CFG = _load_site_cfg(_site_id)
DATA_DIR = ROOT / _CFG["data_dir"]
SOURCES_FILE = ROOT / _CFG["sources_file"]

SOURCES = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))


def fetch_site_icon():
    """Download the site icon from config url and store at config path. Skip if already exists."""
    icon_cfg = _CFG.get("site_icon")
    if not isinstance(icon_cfg, dict):
        return
    url = icon_cfg.get("url", "").strip()
    path = icon_cfg.get("path", "").strip()
    if not url or not path:
        return
    dest = ROOT / path
    if dest.exists():
        return  # already downloaded
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (petfood-watch bot)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(f"Icon downloaded: {dest.relative_to(ROOT)}")
    except Exception as exc:
        print(f"WARN icon download failed ({url}): {exc}", file=sys.stderr)

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


def _title_key(title):
    """Normalised title for duplicate detection: lowercase, strip punctuation/spaces."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


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
    seen_links, seen_titles, unique = set(), set(), []
    for a in articles:
        tk = _title_key(a["title"])
        if a["link"] not in seen_links and tk not in seen_titles:
            seen_links.add(a["link"])
            seen_titles.add(tk)
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


# Fallback briefing: pure stats, no AI
def briefing_fallback(articles):
    from collections import Counter
    counts = Counter(a["category"] for a in articles)
    parts = ", ".join(f"{counts[c]} {c}" for c in ("📈 Market", "🤝 M&A", "⚖️ Regulation", "💡 Innovation") if c in counts)
    return f"{len(articles)} new articles today — {parts}."


BRIEFING_SYSTEM = """You write a structured daily briefing for pet food industry consultants.

From the article summaries below (grouped by category), produce EXACTLY this JSON — no extra keys:
{
  "hook": "One sentence on the overall day (max 150 characters).",
  "categories": {
    "📈 Market": "ONE sentence (max 250 characters) on the main market signal, or null if none.",
    "🤝 M&A": "ONE sentence (max 250 characters) on deals, investments or expansions, or null if none.",
    "⚖️ Regulation": "ONE sentence (max 250 characters) on regulatory developments, or null if none.",
    "💡 Innovation": "ONE sentence (max 250 characters) on product or technology innovation, or null if none."
  }
}

Hard limits:
- Each category value: 250 characters maximum, including spaces. The hook: 150 characters maximum.
- ONE sentence per category, never more. Synthesise the theme; do not enumerate articles.
- Use ONLY what is in the summaries. Do not add names, figures, or facts not present.
- Plain prose only: no lists, no semicolons, no copied titles.
- Reply with valid JSON and nothing else."""


MAX_HOOK_CHARS = 200        # prompt asks for 150 / 250; these margins avoid rejecting a good
MAX_CATEGORY_CHARS = 320    # briefing that is only a few words over


def _briefing_problem(data):
    """Return None if the reply looks like real prose, else a short reason for the rejection."""
    if not isinstance(data, dict):
        return "reply is not a JSON object"
    hook = data.get("hook", "")
    cats = data.get("categories", {})
    if not isinstance(hook, str) or len(hook) < 20:
        return f"hook missing or too short ({hook!r})"
    if not isinstance(cats, dict):
        return "categories is not an object"
    values = [hook] + [v for v in cats.values() if v]
    if any(not isinstance(v, str) for v in values):
        return "a category value is not a string"
    # A title dump is a long run of ';'-separated headlines
    if any(v.count(";") > 3 for v in values):
        return "too many ';' (looks like a list of titles)"
    if len(hook) > MAX_HOOK_CHARS:
        return f"hook too long ({len(hook)} > {MAX_HOOK_CHARS} characters)"
    for name, v in cats.items():
        if v and len(v) > MAX_CATEGORY_CHARS:
            return f"{name} too long ({len(v)} > {MAX_CATEGORY_CHARS} characters)"
    return None


def briefing(articles):
    # Input: up to 6 items per category → 24 items max, ~3K tokens
    # Use ai_summary when available, fall back to title + raw summary.
    cats = {}
    for a in articles:
        cats.setdefault(a["category"], []).append(a)
    input_lines = []
    for cat, items in cats.items():
        input_lines.append(f"\n## {cat}")
        for a in items[:6]:
            text = a.get("ai_summary") or f"{a['title']} — {a.get('summary', '')}"
            input_lines.append(f"- {text}")

    for attempt in range(2):
        text = groq_chat(BRIEFING_SYSTEM, "\n".join(input_lines), max_tokens=1200)
        try:
            data = json.loads(text)
        except Exception:
            print(f"WARN briefing attempt {attempt+1}: JSON parse failed: {str(text)[:200]}", file=sys.stderr)
            continue
        problem = _briefing_problem(data)
        if problem is None:
            return data
        print(f"WARN briefing attempt {attempt+1} rejected: {problem}", file=sys.stderr)
        print(f"     reply was: {text[:300]}", file=sys.stderr)
    return None


# ---------------------------------------------------------------- main

def read_day(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def main():
    from datetime import date as date_type
    now = datetime.now(timezone.utc)
    today_str = f"{now:%Y-%m-%d}"

    fetch_site_icon()
    fetched = load_articles()
    if not fetched:
        print("ERROR: no article fetched, nothing written", file=sys.stderr)
        return 1

    # Load all articles already stored, keyed by link → (path, article).
    stored: dict[str, tuple[Path, dict]] = {}
    for f in DATA_DIR.glob("*/*/*.json"):
        for a in read_day(f):
            if a["link"] not in stored:
                stored[a["link"]] = (f, a)

    # Keep only articles not yet stored (truly new).
    new = [a for a in fetched if a["link"] not in stored]
    if not new:
        print("No new article since previous runs, nothing written")
        return 0

    # Carry over ai_summary from any same-day re-run that already processed them.
    for a in new:
        existing = stored.get(a["link"])
        if existing and existing[1].get("ai_summary"):
            a["ai_summary"] = existing[1]["ai_summary"]

    # Articles without a publication date get the run date as first_seen fallback.
    for a in new:
        if not a.get("date"):
            a["date"] = today_str

    # Summarize new articles.
    n_sum = summarize(new)

    # Group new articles by their publication date.
    by_day: dict[str, list] = {}
    for a in new:
        by_day.setdefault(a["date"][:10], []).append(a)

    # Write/merge each day file.
    written_files = []
    for day_str, arts in by_day.items():
        try:
            d = date_type.fromisoformat(day_str)
        except ValueError:
            d = now.date()
        out = DATA_DIR / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        # Merge with any articles already in that file (e.g. from a previous run).
        existing_in_file = {a["link"]: a for a in read_day(out)}
        for a in arts:
            existing_in_file[a["link"]] = a
        merged = sorted(existing_in_file.values(), key=lambda a: a.get("date") or "", reverse=True)
        out.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        written_files.append((out, len(arts)))
        print(f"Wrote {len(arts)} new articles to {out.relative_to(ROOT)}")

    print(f"Total: {len(new)} new articles ({n_sum} summarized by Groq)")

    # Briefing is written for today's run date (summary of what was fetched today).
    briefing_file = DATA_DIR / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}.briefing.txt"
    briefing_file.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get("GROQ_API_KEY"):
        data = briefing(new)
        if data:
            briefing_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            print(f"Wrote {briefing_file.relative_to(ROOT)}")
        else:
            fb = briefing_fallback(new)
            briefing_file.write_text(json.dumps({"hook": fb, "categories": {}}, ensure_ascii=False), encoding="utf-8")
            print(f"WARN briefing AI failed, wrote fallback to {briefing_file.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
