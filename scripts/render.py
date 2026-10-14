#!/usr/bin/env python3
"""Render the static site from data/YYYY/MM/DD.json and DD.briefing.txt.

Usage: python scripts/render.py <site_dir>

Writes into <site_dir>:
  index.html              articles first seen in the last ROLLING_DAYS days
  archive/YYYY-MM.html    all articles first seen in that month
  archive/index.html      list of monthly archive pages
"""
import hashlib
import html
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SOURCES = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
ROLLING_DAYS = 30
SITE_URL = "https://ibmphilippecabel.github.io/petfood-watch/"
SITE_NAME = "Petfood Watch"
SITE_DESC = ("Daily AI-assisted intelligence on the pet food industry: market, M&A, "
             "regulation and innovation news from trade press, with per-article summaries "
             "and a daily briefing.")
CATEGORIES = ["📈 Market", "🤝 M&A", "⚖️ Regulation", "💡 Innovation"]

CSS = """
  :root { --bg:#f7f8fa; --card:#fff; --border:#e5e7eb; --text:#1f2328; --muted:#57606a; --accent:#3b82d4; --ai:#7c5cd8; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }
  /* header */
  header { background:var(--card); border-bottom:1px solid var(--border); padding:14px 24px; display:flex; justify-content:space-between; align-items:center; }
  header h1 { margin:0; font-size:20px; }
  header nav a { color:var(--accent); text-decoration:none; font-size:14px; margin-left:20px; }
  /* sources dropdown */
  .src-btn { border:1px solid var(--border); background:var(--card); color:var(--text); padding:5px 12px; border-radius:16px; font:inherit; font-size:14px; cursor:pointer; margin-left:20px; }
  .src-btn:hover { border-color:var(--accent); color:var(--accent); }
  .src-dropdown { display:none; position:absolute; right:0; top:calc(100% + 6px); background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 16px; min-width:380px; max-width:520px; box-shadow:0 4px 16px rgba(0,0,0,.08); z-index:100; }
  .src-dropdown.open { display:block; }
  .src-dropdown h3 { margin:0 0 8px; font-size:14px; }
  .src-dropdown ul { padding-left:16px; margin:0; }
  .src-dropdown li { font-size:13px; line-height:1.8; }
  .src-wrap { position:relative; display:inline-flex; align-items:center; }
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
  .ai-icon { font-style:normal; font-size:12px; }
  .hidden { display:none; }
  /* sources list */
  h3 { font-size:16px; margin:8px 0; }
  ul.sources { padding-left:20px; margin:0; }
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
  function initDropdown(btnId, dropId) {
    var btn = document.getElementById(btnId);
    var drop = document.getElementById(dropId);
    if (!btn || !drop) return;
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      drop.classList.toggle('open');
    });
    document.addEventListener('click', function() {
      drop.classList.remove('open');
    });
    drop.addEventListener('click', function(e) { e.stopPropagation(); });
  }
  initDropdown('src-btn', 'src-dropdown');
  initDropdown('arc-btn', 'arc-dropdown');
"""


def esc(v):
    return html.escape(v or "", quote=True)


def art_id(a):
    return "a-" + hashlib.sha1(a["link"].encode("utf-8")).hexdigest()[:10]


def art_day(a):
    return (a.get("date") or "")[:10] or a["first_seen"].isoformat()


def jsonld_tag(obj):
    if not obj:
        return ""
    raw = json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{raw}</script>'


def shell(title, nav_links, body, updated, script="", path="", description=SITE_DESC, jsonld=None, sources_html="", archive_html=""):
    url = SITE_URL + path
    src_btn = (
        f'<div class="src-wrap">'
        f'<button class="src-btn" id="src-btn">📡 Sources</button>'
        f'<div class="src-dropdown" id="src-dropdown">{sources_html}</div>'
        f'</div>'
    ) if sources_html else ""
    arc_btn = (
        f'<div class="src-wrap">'
        f'<button class="src-btn" id="arc-btn">📚 Archive</button>'
        f'<div class="src-dropdown" id="arc-dropdown">{archive_html}</div>'
        f'</div>'
    ) if archive_html else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(url)}">
<link rel="alternate" type="application/atom+xml" title="{SITE_NAME} feed" href="{SITE_URL}feed.xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(url)}">
<meta name="twitter:card" content="summary">
{jsonld_tag(jsonld)}
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>{SITE_NAME}</h1>
  <nav>{nav_links}{arc_btn}{src_btn}</nav>
</header>
<main class="wrap">
{body}
</main>
<footer>Last updated: <time datetime="{updated_iso(updated)}">{updated}</time></footer>
<script>{script}</script>
</body>
</html>
"""


def updated_iso(updated):
    return updated.replace(" UTC", "").replace(" ", "T") + ":00Z"


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
        f'<div class="briefing-label">Daily Briefing — 🤖 AI-generated</div>'
        f'{inner}'
        f'<div class="briefing-meta"><time datetime="{day}">{day}</time></div>'
        f'</div>'
    )


def cards_section(articles):
    buttons = ['<button class="active" data-cat="all">All</button>'] + [
        f'<button data-cat="{esc(c)}">{esc(c)}</button>' for c in CATEGORIES
    ]
    rows = []
    for a in articles:
        d = art_day(a)
        ai = a.get("ai_summary", "")
        ai_html = f'<div class="ai-summary"><span class="ai-icon">🤖</span> {esc(ai)}</div>' if ai else ""
        rows.append(
            f'<article class="card" id="{art_id(a)}" data-cat="{esc(a["category"])}">'
            f'<div class="meta"><span class="tag">{esc(a["category"])}</span>'
            f'<span>{esc(a["source"])}</span><time datetime="{d}">{d}</time></div>'
            f'{ai_html}'
            f'<h2><a href="{esc(a["link"])}" target="_blank" rel="noopener">{esc(a["title"])}</a></h2>'
            f'<p>{esc(a["summary"])}</p></article>'
        )
    grid = "".join(rows) or '<p class="muted">No articles.</p>'
    return f'<nav class="filters">{"".join(buttons)}</nav><div class="grid">{grid}</div>'


def item_list_jsonld(articles, limit=50):
    items = []
    for i, a in enumerate(articles[:limit], 1):
        items.append({
            "@type": "ListItem",
            "position": i,
            "item": {
                "@type": "NewsArticle",
                "headline": a["title"],
                "url": a["link"],
                "datePublished": art_day(a),
                "description": a.get("ai_summary") or a.get("summary", ""),
                "articleSection": a["category"],
                "publisher": {"@type": "Organization", "name": a["source"]},
            },
        })
    return items


def page_jsonld(name, path, description, articles):
    return {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "name": SITE_NAME, "url": SITE_URL,
             "description": SITE_DESC, "inLanguage": "en"},
            {"@type": "CollectionPage", "name": name, "url": SITE_URL + path,
             "description": description, "inLanguage": "en",
             "isPartOf": {"@type": "WebSite", "url": SITE_URL},
             "mainEntity": {"@type": "ItemList", "itemListElement": item_list_jsonld(articles)}},
        ],
    }


def write_machine_files(site, articles, recent, briefing, now):
    # robots.txt
    (site / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        + "".join(f"User-agent: {bot}\nAllow: /\n\n" for bot in (
            "GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot",
            "ClaudeBot", "Google-Extended", "CCBot"))
        + f"Sitemap: {SITE_URL}sitemap.xml\n",
        encoding="utf-8",
    )

    # sitemap.xml
    months = sorted({f"{a['first_seen']:%Y-%m}" for a in articles}, reverse=True)
    today = f"{now:%Y-%m-%d}"
    urls = [("", today), ("archive/index.html", today)] + [
        (f"archive/{ym}.html", today if ym == months[0] else f"{ym}-28") for ym in months
    ]
    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{esc(SITE_URL + p)}</loc><lastmod>{lm}</lastmod></url>\n" for p, lm in urls)
        + "</urlset>\n",
        encoding="utf-8",
    )

    # feed.xml (Atom, 50 latest)
    entries = "".join(
        f'  <entry>\n    <title>{esc(a["title"])}</title>\n'
        f'    <id>{esc(a["link"])}</id>\n'
        f'    <link href="{esc(a["link"])}"/>\n'
        f'    <updated>{art_day(a)}T00:00:00Z</updated>\n'
        f'    <category term="{esc(a["category"])}"/>\n'
        f'    <author><name>{esc(a["source"])}</name></author>\n'
        f'    <summary>{esc(a.get("ai_summary") or a.get("summary", ""))}</summary>\n  </entry>\n'
        for a in recent[:50]
    )
    (site / "feed.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        f'  <title>{SITE_NAME}</title>\n  <subtitle>{esc(SITE_DESC)}</subtitle>\n'
        f'  <link href="{SITE_URL}feed.xml" rel="self"/>\n  <link href="{SITE_URL}"/>\n'
        f'  <id>{SITE_URL}</id>\n  <updated>{updated_iso(f"{now:%Y-%m-%d %H:%M UTC}")}</updated>\n'
        + entries + "</feed>\n",
        encoding="utf-8",
    )

    # data.json (machine-readable copy of the home page)
    (site / "data.json").write_text(
        json.dumps({
            "site": SITE_URL,
            "updated": updated_iso(f"{now:%Y-%m-%d %H:%M UTC}"),
            "briefing": ({"date": briefing[0], **briefing[1]} if briefing else None),
            "articles": [
                {"title": a["title"], "url": a["link"], "source": a["source"],
                 "category": a["category"], "date": art_day(a),
                 "ai_summary": a.get("ai_summary", ""), "excerpt": a.get("summary", "")}
                for a in recent
            ],
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    # llms.txt
    (site / "llms.txt").write_text(
        f"# {SITE_NAME}\n\n"
        f"> {SITE_DESC}\n\n"
        "Content is in English. Articles are collected nightly from public RSS feeds of pet food "
        "trade publications; summaries and the daily briefing are AI-generated, and each item "
        "links to its original source.\n\n"
        "## Main pages\n\n"
        f"- [Home]({SITE_URL}): articles of the last {ROLLING_DAYS} days with the daily briefing\n"
        f"- [Archive]({SITE_URL}archive/index.html): one page per month, all articles\n\n"
        "## Machine-readable\n\n"
        f"- [Atom feed]({SITE_URL}feed.xml): 50 latest articles\n"
        f"- [JSON data]({SITE_URL}data.json): briefing and articles from the last {ROLLING_DAYS} days\n"
        f"- [Sitemap]({SITE_URL}sitemap.xml)\n\n"
        "## Categories\n\n"
        + "".join(f"- {c}\n" for c in CATEGORIES)
        + "\n## Sources\n\n"
        + "".join(f"- [{s['name']}]({s['url']}): {s['description']}\n" for s in SOURCES),
        encoding="utf-8",
    )


def sources_section():
    items = "".join(
        f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["name"])}</a> '
        f'<span class="muted">({esc(s["score"])}/10)</span> — {esc(s["description"])}</li>'
        for s in SOURCES
    )
    return f'<h3>Tracked sources</h3><ul class="sources">{items}</ul>'


def archive_dropdown_html(keys, months=None):
    """keys: ordered list of YYYY-MM strings. months: dict with article counts (optional)."""
    items = "".join(
        f'<li><a href="archive/{esc(ym)}.html">{esc(ym)}</a>'
        + (f' <span class="muted">({len(months[ym])} articles)</span>' if months and ym in months else '')
        + '</li>'
        for ym in keys
    )
    return f'<h3>Archive</h3><ul class="sources">{items}</ul>'


def sources_dropdown_html():
    items = "".join(
        f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["name"])}</a>'
        f' — {esc(s["description"])}</li>'
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
    # first_seen now equals the publication date (build.py files articles by pub date).
    cutoff = now.date() - timedelta(days=ROLLING_DAYS)

    # ── build months dict (by publication date = first_seen path) ────
    months: dict[str, list] = {}
    for a in articles:
        months.setdefault(f"{a['first_seen']:%Y-%m}", []).append(a)

    # ── compute full month list (data + already-published pages) ─────
    archive = site / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    existing_months = {
        p.stem for p in archive.glob("????-??.html")
        if p.stem not in months
    }
    all_months_keys = sorted(set(months) | existing_months, reverse=True)

    # ── index.html (rolling 30 days) ─────────────────────────────────
    recent = [a for a in articles if a["first_seen"] >= cutoff]
    body = briefing_block(briefing) + cards_section(recent)
    nav = '<a href="index.html">🏠 Home</a>'
    home_desc = (briefing[1].get("hook") if briefing else "") or SITE_DESC
    (site / "index.html").write_text(
        shell("Petfood Watch — pet food industry news, market, M&A, regulation", nav, body, updated,
              FILTER_JS, path="", description=home_desc,
              jsonld=page_jsonld(SITE_NAME, "", home_desc, recent),
              sources_html=sources_dropdown_html(),
              archive_html=archive_dropdown_html(all_months_keys, months)),
        encoding="utf-8",
    )

    # ── archive/YYYY-MM.html (one per month) ─────────────────────────

    for ym, items in months.items():
        nav = '<a href="../index.html">🏠 Home</a>'
        body = cards_section(items)
        desc = f"Pet food industry news archive for {ym}: {len(items)} articles."
        (archive / f"{ym}.html").write_text(
            shell(f"Petfood Watch — Archive {ym}", nav, body, updated, FILTER_JS,
                  path=f"archive/{ym}.html", description=desc,
                  jsonld=page_jsonld(f"Petfood Watch archive {ym}", f"archive/{ym}.html", desc, items),
                  archive_html=archive_dropdown_html(all_months_keys, months)),
            encoding="utf-8",
        )

    # ── archive/index.html ───────────────────────────────────────────
    rows = "".join(
        f'<li><a href="{ym}.html">{ym}</a>'
        + (f'<span class="muted">{len(months[ym])} articles</span>' if ym in months else '<span class="muted">—</span>')
        + '</li>'
        for ym in all_months_keys
    )
    nav = '<a href="../index.html">🏠 Home</a>'
    (archive / "index.html").write_text(
        shell("Petfood Watch — Archive", nav, f'<ul class="months">{rows}</ul>', updated,
              path="archive/index.html", description="Monthly archive of Petfood Watch articles.",
              archive_html=archive_dropdown_html(all_months_keys, months)),
        encoding="utf-8",
    )

    write_machine_files(site, articles, recent, briefing, now)

    print(
        f"index.html: {len(recent)} articles (last {ROLLING_DAYS} days); "
        f"{len(months)} monthly archive page(s); briefing={'yes' if briefing else 'no'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
