#!/usr/bin/env python3
"""Fetch RSS feeds of pet food sources, classify articles and generate index.html."""
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
OUTPUT = ROOT / "index.html"
SOURCES_FILE = ROOT / "sources.json"
MAX_PER_SOURCE = 15
MAX_TOTAL = 60
CATEGORIES = ["Marché", "M&A", "Réglementation", "Innovation"]

# Loaded from sources.json: name, url, rss (nullable), description, score, default_category
SOURCES = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))

KEYWORDS = {
    "M&A": [
        "acqui", "merger", "buys", "buyout", "divest", "takeover", "stake",
        "investment", "invests", "funding", "ipo", "joint venture", "acquire",
    ],
    "Réglementation": [
        "regulat", "fda", "aafco", "fediaf", "legislation", "compliance", "labeling",
        "labelling", "recall", "safety", "standard", "ban ", "law", "policy", "eu ",
    ],
    "Innovation": [
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
    for category in ("M&A", "Réglementation", "Innovation"):
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
        except Exception as exc:  # one broken feed must not stop the build
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
                "date": date,
                "category": classify(f"{title} {summary} {tags}", default),
            })
    seen, unique = set(), []
    for a in articles:
        if a["link"] not in seen:
            seen.add(a["link"])
            unique.append(a)
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    unique.sort(key=lambda a: a["date"] or epoch, reverse=True)
    return unique[:MAX_TOTAL]


def esc(value):
    return html.escape(value, quote=True)


def render(articles):
    buttons = ['<button class="active" data-cat="all">Toutes</button>'] + [
        f'<button data-cat="{esc(c)}">{esc(c)}</button>' for c in CATEGORIES
    ]
    cards = []
    for a in articles:
        date = a["date"].strftime("%d/%m/%Y") if a["date"] else ""
        cards.append(
            f'<article class="card" data-cat="{esc(a["category"])}">'
            f'<div class="meta"><span class="tag">{esc(a["category"])}</span>'
            f'<span>{esc(a["source"])}</span><span>{date}</span></div>'
            f'<h2><a href="{esc(a["link"])}" target="_blank" rel="noopener">{esc(a["title"])}</a></h2>'
            f'<p>{esc(a["summary"])}</p></article>'
        )
    sources = "".join(
        f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["name"])}</a> '
        f'<span class="muted">({esc(s["score"])}/10)</span> — {esc(s["description"])}</li>'
        for s in SOURCES
    )
    updated = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    return TEMPLATE.format(
        buttons="\n    ".join(buttons),
        cards="\n    ".join(cards) or '<p class="muted">Aucun article disponible.</p>',
        sources=sources,
        updated=updated,
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Petfood Watch</title>
<style>
  :root {{ --bg:#f7f8fa; --card:#fff; --border:#e5e7eb; --text:#1f2328; --muted:#57606a; --accent:#3b82d4; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }}
  header {{ background:var(--card); border-bottom:1px solid var(--border); padding:24px 16px; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:0 16px; }}
  header .wrap {{ padding:0; }}
  h1 {{ margin:0 0 4px; font-size:24px; }}
  header p {{ margin:0; color:var(--muted); }}
  nav {{ display:flex; flex-wrap:wrap; gap:8px; margin:20px 0; }}
  nav button {{ border:1px solid var(--border); background:var(--card); color:var(--text); padding:6px 14px; border-radius:16px; font:inherit; cursor:pointer; }}
  nav button.active {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; padding-bottom:24px; }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; display:flex; flex-direction:column; gap:8px; }}
  .card h2 {{ margin:0; font-size:16px; line-height:1.4; }}
  .card h2 a {{ color:var(--text); text-decoration:none; }}
  .card h2 a:hover {{ color:var(--accent); }}
  .card p {{ margin:0; color:var(--muted); font-size:14px; }}
  .meta {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; font-size:12px; color:var(--muted); }}
  .tag {{ padding:1px 8px; border:1px solid var(--border); border-radius:10px; color:var(--accent); }}
  .muted {{ color:var(--muted); }}
  .hidden {{ display:none; }}
  h3 {{ font-size:16px; margin:8px 0; }}
  ul {{ padding-left:20px; margin:0 0 32px; }}
  footer {{ text-align:center; color:var(--muted); font-size:12px; padding:16px; border-top:1px solid var(--border); }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>Petfood Watch</h1>
    <p>Hub de veille pet food pour consultants : marché, M&amp;A, réglementation, innovation.</p>
  </div>
</header>

<main class="wrap">
  <nav id="filters">
    {buttons}
  </nav>

  <section class="grid" id="grid">
    {cards}
  </section>

  <h3>Sources suivies</h3>
  <ul>{sources}</ul>
</main>

<footer>Dernière mise à jour : {updated}</footer>

<script>
  var buttons = document.querySelectorAll('#filters button');
  var cards = document.querySelectorAll('#grid .card');
  buttons.forEach(function (btn) {{
    btn.addEventListener('click', function () {{
      buttons.forEach(function (b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      var cat = btn.dataset.cat;
      cards.forEach(function (c) {{
        c.classList.toggle('hidden', cat !== 'all' && c.dataset.cat !== cat);
      }});
    }});
  }});
</script>
</body>
</html>
"""


def main():
    articles = load_articles()
    if not articles:
        print("ERROR: no article fetched, index.html left unchanged", file=sys.stderr)
        return 1
    OUTPUT.write_text(render(articles), encoding="utf-8")
    print(f"index.html written with {len(articles)} articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
