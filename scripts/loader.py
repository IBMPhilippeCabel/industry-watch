"""Reads the articles and the latest briefing a site's build.py wrote under its data directory."""
import json
import re
from datetime import date


def _title_key(title):
    """Normalised title for duplicate detection: lowercase, strip punctuation/spaces."""
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def load_all(data_dir):
    """Return (articles deduplicated by link, latest briefing as (YYYY-MM-DD, text) or None)."""
    seen_links = {}   # link → article
    seen_titles = {}  # title_key → article
    for f in sorted(data_dir.glob("*/*/*.json")):  # oldest day first
        day = date(int(f.parent.parent.name), int(f.parent.name), int(f.stem))
        try:
            arts = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for a in arts:
            tk = _title_key(a.get("title", ""))
            if a["link"] not in seen_links and tk not in seen_titles:
                a["first_seen"] = day
                seen_links[a["link"]] = a
                seen_titles[tk] = a
    articles = list(seen_links.values())
    articles.sort(key=lambda a: (a.get("date") or a["first_seen"].isoformat()), reverse=True)

    briefing = None
    files = sorted(data_dir.glob("*/*/*.briefing.txt"))
    if files:
        f = files[-1]
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            data = None   # old plain-text format (title dump): ignored
        if isinstance(data, dict) and (data.get("hook") or data.get("categories")):
            briefing = (f"{f.parent.parent.name}-{f.parent.name}-{f.name.split('.')[0]}", data)
    return articles, briefing
