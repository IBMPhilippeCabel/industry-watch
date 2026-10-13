#!/usr/bin/env python3
"""Render the static site from data/YYYY/MM/DD.json and DD.briefing.txt.

Usage: python scripts/render.py <site_dir>

Writes into <site_dir>:
  index.html              articles first seen in the last ROLLING_DAYS days
  archive/YYYY-MM.html    all articles first seen in that month
  archive/index.html      list of monthly archive pages
"""
import html
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SOURCES = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
ROLLING_DAYS = 30
CATEGORIES = ["📈 Market", "🤝 M&A", "⚖️ Regulation", "💡 Innovation"]

CSS = """
  :root { --bg:#f7f8fa; --card:#fff; --border:#e5e7eb; --text:#1f2328; --muted:#57606a; --accent:#3b82d4; --ai:#7c5cd8; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }
  /* header */
  header { background:var(--card); border-bottom:1px solid var(--border); padding:14px 24px; display:flex; justify-content:space-between; align-items:center; }
  header h1 { margin:0; font-size:20px; }
  header nav a { color:var(--accent); text-decoration:none; font-size:14px; margin-left:20px; }
  /* layout */
  .wrap { max-width:1100px; margin:0 auto; padding:0 24px; }
  a { color:var(--accent); text-decoration:none; }
  /* briefing */
  .briefing { background:var(--card); border:1px solid var(--border); border-left:4px solid var(--ai); border-radius:8px; padding:16px 20px; margin:20px 0 4px; }
  .briefing-label { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.06em; color:var(--ai); margin-bottom:6px; }
  .briefing p { margin:0 0 6px; font-size:14px; line-height:1.6; }
  .briefing .briefing-hook { font-size:15px; font-weight:600; margin-bottom:10px; }
  .briefing .briefing-cat { color:var(--text); }
  .briefing-meta { font-size:12px; color:var(--muted); margin-top:8px; }
  /* filters */
  nav.filters { display:flex; flex-wrap:wrap; gap:8px; margin:16px 0; }
  nav.filters button { border:1px solid var(--border); background:var(--card); color:var(--text); padding:6px 14px; border-radius:16px; font:inherit; cursor:pointer; }
  nav.filters button.active { background:var(--accent); border-color:var(--accent); color:#fff; }
  /* grid */
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; padding-bottom:24px; }
  /* card */
  .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; display:flex; flex-direction:column; gap:6px; }
  .card h2 { margin:0; font-size:15px; line-height:1.4; }
  .card h2 a { color:var(--text); }
  .card h2 a:hover { color:var(--accent); }
  .card p { margin:0; color:var(--muted); font-size:13px; }
  .meta { display:flex; flex-wrap:wrap; gap:8px; align-items:center; font-size:12px; color:var(--muted); }
  .tag { padding:1px 8px; border:1px solid var(--border); border-radius:10px; color:var(--accent); font-size:12px; }
  .ai-summary { font-size:13px; color:var(--muted); font-style:italic; border-left:3px solid var(--ai); padding-left:8px; line-height:1.5; }
  .hidden { display:none; }
  /* sources list */
  h3 { font-size:16px; margin:8px 0; }
  ul.sources { padding-left:20px; margin:0 0 32px; }
  /* archive list */
  ul.months { list-style:none; padding:0; margin:20px 0 32px; max-width:600px; }
  ul.months li { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:10px 16px; margin-bottom:8px; display:flex; justify-content:space-between; }
  .muted { color:var(--muted); }
  footer { text-align:center; color:var(--muted); font-size:12px; padding:16px; border-top:1px solid var(--border); }
"""

FILTER_JS = """
  var buttons = document.querySelectorAll('nav.filters button');
  var cards = document.querySelectorAll('.grid .card');
  buttons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      buttons.forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var cat = btn.dataset.cat;
      cards.forEach(function(c) {
        c.classList.toggle('hidden', cat !== 'all' && c.dataset.cat !== cat);
      });
    });
  });
"""


def esc(v):
    return html.escape(v or "", quote=True)


def shell(title, nav_links, body, updated, script=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Petfood Watch</h1>
  <nav>{nav_links}</nav>
</header>
<div class="wrap">
{body}
</div>
<footer>Last updated: {updated}</footer>
<script>{script}</script>
</body>
</html>
"""


def briefing_block(briefing):
    if not briefing:
        return ""
    day, data = briefing
    hook = data.get("hook", "")
    cats = data.get("categories", {})
    # hook line
    parts = [f'<p class="briefing-hook">{esc(hook)}</p>'] if hook else []
    # one line per category that has content
    for cat in ("📈 Market", "🤝 M&A", "⚖️ Regulation", "💡 Innovation"):
        v = cats.get(cat)
        if v:
            parts.append(f'<p class="briefing-cat"><strong>{esc(cat)}</strong> — {esc(v)}</p>')
    if not parts:
        return ""
    inner = "\n".join(parts)
    return (
        f'<div class="briefing">'
        f'<div class="briefing-label">✦ Daily Briefing — AI-generated</div>'
        f'{inner}'
        f'<div class="briefing-meta">{day}</div>'
        f'</div>'
    )


def cards_section(articles):
    buttons = ['<button class="active" data-cat="all">All</button>'] + [
        f'<button data-cat="{esc(c)}">{esc(c)}</button>' for c in CATEGORIES
    ]
    rows = []
    for a in articles:
        d = (a.get("date") or "")[:10]
        ai = a.get("ai_summary", "")
        ai_html = f'<div class="ai-summary">{esc(ai)}</div>' if ai else ""
        rows.append(
            f'<article class="card" data-cat="{esc(a["category"])}">'
            f'<div class="meta"><span class="tag">{esc(a["category"])}</span>'
            f'<span>{esc(a["source"])}</span><span>{d}</span></div>'
            f'{ai_html}'
            f'<h2><a href="{esc(a["link"])}" target="_blank" rel="noopener">{esc(a["title"])}</a></h2>'
            f'<p>{esc(a["summary"])}</p></article>'
        )
    grid = "".join(rows) or '<p class="muted">No articles.</p>'
    return f'<nav class="filters">{"".join(buttons)}</nav><div class="grid">{grid}</div>'


def sources_section():
    items = "".join(
        f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["name"])}</a> '
        f'<span class="muted">({esc(s["score"])}/10)</span> — {esc(s["description"])}</li>'
        for s in SOURCES
    )
    return f'<h3>Tracked sources</h3><ul class="sources">{items}</ul>'


def load_all():
    """Return (articles deduplicated by link, latest briefing as (YYYY-MM-DD, text) or None)."""
    seen = {}
    for f in sorted(DATA_DIR.glob("*/*/*.json")):  # oldest day first
        day = date(int(f.parent.parent.name), int(f.parent.name), int(f.stem))
        try:
            arts = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for a in arts:
            if a["link"] not in seen:
                a["first_seen"] = day
                seen[a["link"]] = a
    articles = list(seen.values())
    articles.sort(key=lambda a: (a.get("date") or a["first_seen"].isoformat()), reverse=True)

    briefing = None
    files = sorted(DATA_DIR.glob("*/*/*.briefing.txt"))
    if files:
        f = files[-1]
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            data = None   # old plain-text format (title dump): ignored
        if isinstance(data, dict) and (data.get("hook") or data.get("categories")):
            briefing = (f"{f.parent.parent.name}-{f.parent.name}-{f.name.split('.')[0]}", data)
    return articles, briefing


def main():
    if len(sys.argv) < 2:
        print("Usage: render.py <site_dir>", file=sys.stderr)
        return 2
    site = Path(sys.argv[1]).resolve()
    articles, briefing = load_all()
    if not articles:
        print("ERROR: no data found in data/", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    updated = f"{now:%Y-%m-%d %H:%M UTC}"
    cutoff = now.date() - timedelta(days=ROLLING_DAYS)

    # ── index.html (rolling 30 days) ─────────────────────────────────
    recent = [a for a in articles if a["first_seen"] >= cutoff]
    body = briefing_block(briefing) + cards_section(recent) + sources_section()
    nav = '<a href="index.html">🏠 Home</a><a href="archive/index.html">📚 Archive</a>'
    (site / "index.html").write_text(
        shell("Petfood Watch", nav, body, updated, FILTER_JS),
        encoding="utf-8",
    )

    # ── archive/YYYY-MM.html (one per month) ─────────────────────────
    archive = site / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    months: dict[str, list] = {}
    for a in articles:
        months.setdefault(f"{a['first_seen']:%Y-%m}", []).append(a)
    for ym, items in months.items():
        nav = '<a href="../index.html">🏠 Home</a><a href="index.html">📚 Archive</a>'
        body = cards_section(items)
        (archive / f"{ym}.html").write_text(
            shell(f"Petfood Watch — {ym}", nav, body, updated, FILTER_JS),
            encoding="utf-8",
        )

    # ── archive/index.html ───────────────────────────────────────────
    rows = "".join(
        f'<li><a href="{ym}.html">{ym}</a><span class="muted">{len(months[ym])} articles</span></li>'
        for ym in sorted(months, reverse=True)
    )
    nav = '<a href="../index.html">🏠 Home</a><a href="index.html">📚 Archive</a>'
    (archive / "index.html").write_text(
        shell("Petfood Watch — Archive", nav, f'<ul class="months">{rows}</ul>', updated),
        encoding="utf-8",
    )

    print(
        f"index.html: {len(recent)} articles (last {ROLLING_DAYS} days); "
        f"{len(months)} monthly archive page(s); briefing={'yes' if briefing else 'no'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
