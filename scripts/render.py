#!/usr/bin/env python3
"""Render the static site from data/YYYY/MM/DD.json.

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
  :root { --bg:#f7f8fa; --card:#fff; --border:#e5e7eb; --text:#1f2328; --muted:#57606a; --accent:#3b82d4; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }
  header { background:var(--card); border-bottom:1px solid var(--border); padding:24px 16px; }
  .wrap { max-width:1100px; margin:0 auto; padding:0 16px; }
  header .wrap { padding:0; }
  h1 { margin:0 0 4px; font-size:24px; }
  header p { margin:0; color:var(--muted); }
  a { color:var(--accent); text-decoration:none; }
  .links { margin-top:8px; font-size:14px; }
  .links a { margin-right:16px; }
  nav { display:flex; flex-wrap:wrap; gap:8px; margin:20px 0; }
  nav button { border:1px solid var(--border); background:var(--card); color:var(--text); padding:6px 14px; border-radius:16px; font:inherit; cursor:pointer; }
  nav button.active { background:var(--accent); border-color:var(--accent); color:#fff; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; padding-bottom:24px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; display:flex; flex-direction:column; gap:8px; }
  .card h2 { margin:0; font-size:16px; line-height:1.4; }
  .card h2 a { color:var(--text); }
  .card h2 a:hover { color:var(--accent); }
  .card p { margin:0; color:var(--muted); font-size:14px; }
  .meta { display:flex; flex-wrap:wrap; gap:8px; align-items:center; font-size:12px; color:var(--muted); }
  .tag { padding:1px 8px; border:1px solid var(--border); border-radius:10px; color:var(--accent); }
  .muted { color:var(--muted); }
  .hidden { display:none; }
  h3 { font-size:16px; margin:8px 0; }
  ul.sources { padding-left:20px; margin:0 0 32px; }
  ul.months { list-style:none; padding:0; margin:20px 0 32px; max-width:600px; }
  ul.months li { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:10px 16px; margin-bottom:8px; display:flex; justify-content:space-between; }
  footer { text-align:center; color:var(--muted); font-size:12px; padding:16px; border-top:1px solid var(--border); }
"""

FILTER_JS = """
  var buttons = document.querySelectorAll('#filters button');
  var cards = document.querySelectorAll('#grid .card');
  buttons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      buttons.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var cat = btn.dataset.cat;
      cards.forEach(function (c) {
        c.classList.toggle('hidden', cat !== 'all' && c.dataset.cat !== cat);
      });
    });
  });
"""


def esc(value):
    return html.escape(value or "", quote=True)


def page(title, subtitle, links, body, updated, script=""):
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
  <div class="wrap">
    <h1>{esc(title)}</h1>
    <p>{subtitle}</p>
    <p class="links">{links}</p>
  </div>
</header>
<main class="wrap">
{body}
</main>
<footer>Last updated: {updated}</footer>
<script>{script}</script>
</body>
</html>
"""


def articles_body(articles, with_sources):
    buttons = ['<button class="active" data-cat="all">All</button>'] + [
        f'<button data-cat="{esc(c)}">{esc(c)}</button>' for c in CATEGORIES
    ]
    cards = []
    for a in articles:
        d = (a.get("date") or "")[:10]
        cards.append(
            f'<article class="card" data-cat="{esc(a["category"])}">'
            f'<div class="meta"><span class="tag">{esc(a["category"])}</span>'
            f'<span>{esc(a["source"])}</span><span>{d}</span></div>'
            f'<h2><a href="{esc(a["link"])}" target="_blank" rel="noopener">{esc(a["title"])}</a></h2>'
            f'<p>{esc(a["summary"])}</p></article>'
        )
    body = (
        f'<nav id="filters">{"".join(buttons)}</nav>\n'
        f'<section class="grid" id="grid">{"".join(cards) or "<p class=muted>No articles.</p>"}</section>'
    )
    if with_sources:
        items = "".join(
            f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["name"])}</a> '
            f'<span class="muted">({esc(s["score"])}/10)</span> — {esc(s["description"])}</li>'
            for s in SOURCES
        )
        body += f'\n<h3>Tracked sources</h3>\n<ul class="sources">{items}</ul>'
    return body


def load_first_seen():
    """Return articles deduplicated by link, each tagged with the first day it was stored."""
    seen = {}
    for f in sorted(DATA_DIR.glob("*/*/*.json")):  # oldest day first
        day = date(int(f.parent.parent.name), int(f.parent.name), int(f.stem))
        for a in json.loads(f.read_text(encoding="utf-8")):
            if a["link"] not in seen:
                a["first_seen"] = day
                seen[a["link"]] = a
    articles = list(seen.values())
    articles.sort(key=lambda a: (a.get("date") or a["first_seen"].isoformat()), reverse=True)
    return articles


def main():
    if len(sys.argv) < 2:
        print("Usage: render.py <site_dir>", file=sys.stderr)
        return 2
    site = Path(sys.argv[1]).resolve()
    articles = load_first_seen()
    if not articles:
        print("ERROR: no data found in data/", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    updated = f"{now:%Y-%m-%d %H:%M UTC}"
    cutoff = now.date() - timedelta(days=ROLLING_DAYS)

    # Rolling index
    recent = [a for a in articles if a["first_seen"] >= cutoff]
    (site / "index.html").write_text(
        page(
            "Petfood Watch",
            f"Pet food intelligence hub for consultants. Last {ROLLING_DAYS} days "
            f"({len(recent)} articles).",
            '<a href="archive/index.html">Archive</a>',
            articles_body(recent, with_sources=True),
            updated,
            FILTER_JS,
        ),
        encoding="utf-8",
    )

    # Monthly archive pages
    archive = site / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    months = {}
    for a in articles:
        months.setdefault(f"{a['first_seen']:%Y-%m}", []).append(a)
    for ym, items in months.items():
        (archive / f"{ym}.html").write_text(
            page(
                f"Petfood Watch - {ym}",
                f"{len(items)} articles first seen in {ym}.",
                '<a href="../index.html">Latest</a><a href="index.html">Archive</a>',
                articles_body(items, with_sources=False),
                updated,
                FILTER_JS,
            ),
            encoding="utf-8",
        )

    rows = "".join(
        f'<li><a href="{ym}.html">{ym}</a><span class="muted">{len(months[ym])} articles</span></li>'
        for ym in sorted(months, reverse=True)
    )
    (archive / "index.html").write_text(
        page(
            "Petfood Watch - Archive",
            "One page per month.",
            '<a href="../index.html">Latest</a>',
            f'<ul class="months">{rows}</ul>',
            updated,
        ),
        encoding="utf-8",
    )
    print(f"index.html: {len(recent)} articles (last {ROLLING_DAYS} days); {len(months)} monthly archive page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
