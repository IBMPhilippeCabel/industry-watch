#!/usr/bin/env python3
"""Render the static site from data/YYYY/MM/DD.json and DD.briefing.txt.

Usage: python scripts/render.py [--site <id>] <output_dir>

For a given site id, writes into <output_dir>/<id>/:
  index.html              articles of the last ROLLING_DAYS days
  archive/YYYY-MM.html    all articles for that month
  archive/index.html      list of monthly archive pages

Also writes <output_dir>/index.html  (portal entry page listing all sites).
"""
import hashlib
import html
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def _load_site_cfg(cfg, site_id=None):
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

_GLOBAL_CFG = _load_config()
_CFG = _load_site_cfg(_GLOBAL_CFG, _site_id)

GOATCOUNTER_URL = _GLOBAL_CFG.get("goatcounter_url", "")
_GC_SNIPPET = (
    f'<script data-goatcounter="{GOATCOUNTER_URL}" async src="//gc.zgo.at/count.js"></script>'
    if GOATCOUNTER_URL else ""
)

DATA_DIR   = ROOT / _CFG["data_dir"]
SOURCES    = json.loads((ROOT / _CFG["sources_file"]).read_text(encoding="utf-8"))
ROLLING_DAYS = int(_CFG.get("rolling_days", 30))
SITE_NAME  = _CFG["site_name"]
SITE_DESC  = _CFG["site_description"]
SITE_URL   = _GLOBAL_CFG["site_root_url"].rstrip("/") + "/" + _CFG["id"] + "/"
def _extract_categories():
    if _CFG.get("categories"):
        return _CFG["categories"]
    cats = []
    for s in SOURCES:
        c = s.get("default_category")
        if c and c not in cats:
            cats.append(c)
    return cats or ["📈 Market", "🤝 M&A", "⚖️ Regulation", "💡 Innovation"]

CATEGORIES = _extract_categories()

CSS = """
  :root { --bg:#f7f8fa; --card:#fff; --border:#e5e7eb; --text:#1f2328; --muted:#57606a; --accent:#3b82d4; --ai:#7c5cd8; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }
  /* header */
  header { background:var(--card); border-bottom:1px solid var(--border); padding:14px 24px; display:flex; justify-content:space-between; align-items:center; }
  header h1 { margin:0; font-size:20px; display:flex; align-items:center; gap:10px; }
  header h1 img { width:28px; height:28px; object-fit:contain; border-radius:4px; }
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
  .page-updated { font-size:12px; color:var(--muted); margin:12px 0 4px; }
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
  initDropdown('sites-btn', 'sites-dropdown');
"""


def esc(v):
    return html.escape(v or "", quote=True)


def _title_key(title):
    """Normalised title for duplicate detection: lowercase, strip punctuation/spaces."""
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def art_id(a):
    return "a-" + hashlib.sha1(a["link"].encode("utf-8")).hexdigest()[:10]


def art_day(a):
    return (a.get("date") or "")[:10] or a["first_seen"].isoformat()


def jsonld_tag(obj):
    if not obj:
        return ""
    raw = json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{raw}</script>'


def _icon_src(icon_cfg):
    """Resolve icon src in order: local path (if file exists) → url → None.
    Returns a URL/path string usable in HTML, or None."""
    if not isinstance(icon_cfg, dict):
        return None
    local = icon_cfg.get("path", "").strip()
    if local and (ROOT / local).exists():
        # Just the filename — icon is copied into site/<id>/ at render time
        return Path(local).name
    url = icon_cfg.get("url", "").strip()
    return url or None


def _site_header_icon():
    """Return an <img> tag (path→url resolution), no fallback to emoji."""
    icon_cfg = _CFG.get("site_icon")
    src = _icon_src(icon_cfg)
    if not src:
        return ""
    name = esc(_CFG.get("site_name", ""))
    return f'<img src="{esc(src)}" alt="{name}" onerror="this.style.display=\'none\'">'


def _sites_dropdown_html(depth=1):
    """List all sites as links for the header dropdown. depth=1 for site pages, 2 for archive pages."""
    prefix = "../" * depth
    root_url = _GLOBAL_CFG["site_root_url"].rstrip("/") + "/"
    items = ""
    for s in _GLOBAL_CFG["sites"]:
        sid = s["id"]
        status = s.get("status", "live")
        name = esc(s["site_name"])
        icon_cfg = s.get("site_icon")
        src = _icon_src(icon_cfg)
        img = (
            f'<img src="{esc(src)}" alt="" onerror="this.style.display=\'none\'" '
            f'style="width:16px;height:16px;object-fit:contain;border-radius:3px;vertical-align:middle;margin-right:6px;">'
        ) if src else ""
        wip = " 🚧" if status == "under_construction" else ""
        active = " style=\"font-weight:700;color:var(--text);\"" if sid == _CFG["id"] else ""
        items += f'<li><a href="{esc(prefix)}{esc(sid)}/index.html"{active}>{img}{name}{wip}</a></li>'
    return f'<ul class="sources" style="min-width:200px">{items}</ul>'


def shell(title, nav_links, body, updated, script="", path="", description=SITE_DESC, jsonld=None, sources_html="", archive_html="", depth=1):
    url = SITE_URL + path
    sites_btn = (
        f'<div class="src-wrap">'
        f'<button class="src-btn" id="sites-btn">🗂️ Sites</button>'
        f'<div class="src-dropdown" id="sites-dropdown">{_sites_dropdown_html(depth)}</div>'
        f'</div>'
    )
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
    stats_prefix = "../" * (depth - 1)
    stats_btn = f'<a href="{stats_prefix}stats.html" class="src-btn">📊 Stats</a>'
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
  <h1>{_site_header_icon()}{esc(SITE_NAME)}</h1>
  <nav>{nav_links}{stats_btn}{sites_btn}{arc_btn}{src_btn}</nav>
</header>
<main class="wrap">
{body}
</main>
<footer>Last updated: <time datetime="{updated_iso(updated)}">{updated}</time></footer>
<script>{script}</script>
{_GC_SNIPPET}
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
    months = sorted({(a.get("date") or a["first_seen"].isoformat())[:7] for a in articles}, reverse=True)
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
    seen_links = {}   # link → article
    seen_titles = {}  # title_key → article
    for f in sorted(DATA_DIR.glob("*/*/*.json")):  # oldest day first
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


def _resolve_icon(icon_cfg, default_emoji="🌐"):
    """Return HTML for an icon: path→url→default emoji fallback.
    icon_cfg: plain string (emoji) or {"default":"🐾","url":"...","path":"..."}.
    """
    if not icon_cfg:
        return esc(default_emoji)
    if isinstance(icon_cfg, str):
        return esc(icon_cfg)
    emoji = esc(icon_cfg.get("default") or default_emoji)
    src = _icon_src(icon_cfg)
    if not src:
        return emoji
    return (
        f'<img src="{esc(src)}" alt="{emoji}" style="width:20px;height:20px;object-fit:contain;border-radius:3px;vertical-align:middle;" '
        f'onerror="this.replaceWith(document.createTextNode(\'{emoji}\'))">'
    )


def render_under_construction(site, updated, portal_url="../index.html"):
    """Write a single index.html under-construction page for a site."""
    name = esc(SITE_NAME)
    img_tag = _site_header_icon()
    site.mkdir(parents=True, exist_ok=True)
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — Under Construction</title>
<style>
  body {{ margin:0; font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif; background:#f7f8fa; color:#1f2328; }}
  .wrap {{ max-width:520px; margin:100px auto; padding:0 24px; text-align:center; }}
  .icon {{ font-size:56px; margin-bottom:16px; display:flex; justify-content:center; align-items:center; gap:12px; }}
  .icon img {{ width:56px; height:56px; object-fit:contain; border-radius:8px; }}
  h1 {{ font-size:24px; margin-bottom:8px; }}
  p {{ color:#57606a; margin-bottom:32px; }}
  .badge {{ display:inline-block; background:#fef3c7; color:#92400e; border:1px solid #fde68a; border-radius:20px; padding:4px 14px; font-size:13px; font-weight:600; margin-bottom:24px; }}
  .btn {{ display:inline-block; background:#3b82d4; color:#fff; border-radius:8px; padding:10px 24px; text-decoration:none; font-size:14px; font-weight:600; }}
  .btn:hover {{ background:#2563b0; }}
  footer {{ text-align:center; color:#57606a; font-size:12px; padding:16px; border-top:1px solid #e5e7eb; margin-top:60px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="icon">{img_tag} 🚧</div>
  <h1>{name}</h1>
  <div class="badge">Under Construction</div>
  <p>This site is currently being set up. Check back soon!</p>
  <a href="{esc(portal_url)}" class="btn">← Back to portal</a>
</div>
<footer>Last updated: <time>{updated}</time></footer>
{_GC_SNIPPET}
</body>
</html>
"""
    (site / "index.html").write_text(html_out, encoding="utf-8")
    print(f"[{_CFG['id']}] under-construction page written")


def _portal_header_icon():
    """Return an <img> or fallback emoji for the main portal header."""
    icon_cfg = _GLOBAL_CFG.get("portal_icon")
    src = _icon_src(icon_cfg)
    if not src:
        emoji = esc(icon_cfg.get("default", "📡")) if isinstance(icon_cfg, dict) else "📡"
        return f'<span style="margin-right:8px;">{emoji}</span>'
    return f'<img src="{esc(src)}" alt="" style="width:28px;height:28px;object-fit:contain;border-radius:6px;vertical-align:middle;margin-right:10px;">'


def render_portal(output_dir, updated):
    """Generate the portal entry page listing all sites."""
    cfg = _GLOBAL_CFG
    portal_name = cfg.get("portal_name", "Industry Watch")
    portal_desc = cfg.get("portal_description", "")
    root_url = cfg["site_root_url"].rstrip("/") + "/"

    p_icon_cfg = cfg.get("portal_icon")
    if isinstance(p_icon_cfg, dict):
        local = p_icon_cfg.get("path", "").strip()
        if local:
            src_icon = ROOT / local
            if src_icon.exists():
                import shutil
                shutil.copy2(src_icon, output_dir / src_icon.name)

    cards = ""
    for s in cfg["sites"]:
        sid = s["id"]
        status = s.get("status", "live")
        icon = _resolve_icon(s.get("site_icon"), "🌐")
        name = esc(s["site_name"])
        desc = esc(s["site_description"])
        url = esc(sid + "/index.html")
        badge = '<span class="portal-badge">🚧 Under construction</span>' if status == "under_construction" else ""
        extra_cls = " portal-card--wip" if status == "under_construction" else ""
        cards += (
            f'<a href="{url}" class="portal-card{extra_cls}">'
            f'<div class="portal-icon">{icon}</div>'
            f'<div class="portal-name">{name}{badge}</div>'
            f'<div class="portal-desc">{desc}</div>'
            f'</a>'
        )

    portal_css = """
  body { margin:0; font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif; background:#f7f8fa; color:#1f2328; }
  header { background:#fff; border-bottom:1px solid #e5e7eb; padding:14px 24px; display:flex; justify-content:space-between; align-items:center; }
  header h1 { margin:0; font-size:20px; font-weight:700; color:#1f2328; display:flex; align-items:center; }
  .stats-btn { border:1px solid #e5e7eb; background:#fff; color:#3b82d4; padding:6px 16px; border-radius:16px; font:inherit; font-size:14px; cursor:pointer; text-decoration:none; font-weight:600; }
  .stats-btn:hover { background:#3b82d4; color:#fff; border-color:#3b82d4; }
  .portal-wrap { max-width:800px; margin:40px auto; padding:0 24px; text-align:center; }
  .portal-updated { font-size:12px; color:#57606a; margin:0 0 28px; letter-spacing:.01em; }
  .portal-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:20px; text-align:left; }
  .portal-card { display:block; background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:24px; text-decoration:none; color:#1f2328; transition:border-color .15s; }
  .portal-card:hover { border-color:#3b82d4; }
  .portal-card--wip { background:#fffbeb; border-color:#fde68a; }
  .portal-card--wip:hover { border-color:#f59e0b; }
  .portal-icon { font-size:32px; margin-bottom:12px; display:flex; align-items:center; }
  .portal-icon img { width:40px; height:40px; object-fit:contain; border-radius:6px; }
  .portal-name { font-size:18px; font-weight:600; margin-bottom:6px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .portal-badge { font-size:11px; font-weight:600; background:#fef3c7; color:#92400e; border:1px solid #fde68a; border-radius:20px; padding:2px 8px; }
  .portal-desc { font-size:13px; color:#57606a; line-height:1.5; }
  footer { text-align:center; color:#57606a; font-size:12px; padding:16px; border-top:1px solid #e5e7eb; margin-top:40px; }
"""
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(portal_name)}</title>
<meta name="description" content="{esc(portal_desc)}">
<style>{portal_css}</style>
</head>
<body>
<header>
  <h1>{_portal_header_icon()}{esc(portal_name)}</h1>
  <nav><a href="stats.html" class="stats-btn">📊 Stats</a></nav>
</header>
<div class="portal-wrap">
  <p class="portal-updated">Last updated: <time>{updated}</time></p>
  <div class="portal-grid">{cards}</div>
</div>
<footer>Last updated: <time>{updated}</time></footer>
{_GC_SNIPPET}
</body>
</html>
"""
    (output_dir / "index.html").write_text(html_out, encoding="utf-8")
    print(f"Portal index.html written ({len(cfg['sites'])} sites)")


def main():
    # Parse args: render.py [--site <id>] <output_dir>
    args = [a for a in sys.argv[1:] if a != "--site" and a != _site_id]
    if not args:
        print("Usage: render.py [--site <id>] <output_dir>", file=sys.stderr)
        return 2
    output_dir = Path(args[0]).resolve()

    # Site output goes into output_dir/<id>/
    site = output_dir / _CFG["id"]
    site.mkdir(parents=True, exist_ok=True)

    # Copy local icon into site dir so relative src works after deploy.
    icon_cfg = _CFG.get("site_icon")
    if isinstance(icon_cfg, dict):
        local = icon_cfg.get("path", "").strip()
        if local:
            src_icon = ROOT / local
            if src_icon.exists():
                import shutil
                shutil.copy2(src_icon, site / src_icon.name)

    now = datetime.now(timezone.utc)
    updated = f"{now:%Y-%m-%d %H:%M UTC}"
    portal_url = _GLOBAL_CFG["site_root_url"].rstrip("/") + "/"

    # If under construction: write placeholder page and skip full render.
    if _CFG.get("status") == "under_construction":
        render_under_construction(site, updated)
        render_portal(output_dir, updated)
        return 0

    articles, briefing = load_all()
    if not articles:
        print("ERROR: no data found in data/", file=sys.stderr)
        return 1

    cutoff = now.date() - timedelta(days=ROLLING_DAYS)

    # ── build months dict (by publication date) ───────────────────────
    months: dict[str, list] = {}
    for a in articles:
        pub = (a.get("date") or a["first_seen"].isoformat())[:7]  # YYYY-MM
        months.setdefault(pub, []).append(a)

    # ── compute full month list (data + already-published pages) ─────
    archive = site / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    existing_months = {
        p.stem for p in archive.glob("????-??.html")
        if p.stem not in months
    }
    all_months_keys = sorted(set(months) | existing_months, reverse=True)

    # ── <id>/index.html (rolling N days) ─────────────────────────────
    recent = [a for a in articles if (a.get("date") or a["first_seen"].isoformat())[:10] >= cutoff.isoformat()]
    updated_line = f'<p class="page-updated">Last updated: <time datetime="{updated_iso(updated)}">{updated}</time></p>'
    body = updated_line + briefing_block(briefing) + cards_section(recent)
    nav = f'<a href="../index.html">🏠 Portal</a>'
    home_desc = (briefing[1].get("hook") if briefing else "") or SITE_DESC
    (site / "index.html").write_text(
        shell(f"{SITE_NAME} — news", nav, body, updated,
              FILTER_JS, path=f"{_CFG['id']}/", description=home_desc,
              jsonld=page_jsonld(SITE_NAME, f"{_CFG['id']}/", home_desc, recent),
              sources_html=sources_dropdown_html(),
              archive_html=archive_dropdown_html(all_months_keys, months)),
        encoding="utf-8",
    )

    # ── <id>/archive/YYYY-MM.html ─────────────────────────────────────
    for ym, items in months.items():
        nav = f'<a href="../../index.html">🏠 Portal</a>'
        body = updated_line + cards_section(items)
        desc = f"{SITE_NAME} archive {ym}: {len(items)} articles."
        (archive / f"{ym}.html").write_text(
            shell(f"{SITE_NAME} — Archive {ym}", nav, body, updated, FILTER_JS,
                  path=f"{_CFG['id']}/archive/{ym}.html", description=desc,
                  jsonld=page_jsonld(f"{SITE_NAME} archive {ym}", f"{_CFG['id']}/archive/{ym}.html", desc, items),
                  archive_html=archive_dropdown_html(all_months_keys, months),
                  depth=2),
            encoding="utf-8",
        )

    # ── <id>/archive/index.html ───────────────────────────────────────
    rows = "".join(
        f'<li><a href="{ym}.html">{ym}</a>'
        + (f'<span class="muted">{len(months[ym])} articles</span>' if ym in months else '<span class="muted">—</span>')
        + '</li>'
        for ym in all_months_keys
    )
    nav = f'<a href="../../index.html">🏠 Portal</a>'
    (archive / "index.html").write_text(
        shell(f"{SITE_NAME} — Archive", nav, f'<ul class="months">{rows}</ul>', updated,
              path=f"{_CFG['id']}/archive/index.html",
              description=f"Monthly archive of {SITE_NAME} articles.",
              archive_html=archive_dropdown_html(all_months_keys, months),
              depth=2),
        encoding="utf-8",
    )

    write_machine_files(site, articles, recent, briefing, now)

    # ── portal index.html (always regenerated, lists all sites) ──────
    render_portal(output_dir, updated)

    print(
        f"[{_CFG['id']}] index.html: {len(recent)} articles (last {ROLLING_DAYS} days); "
        f"{len(months)} monthly archive page(s); briefing={'yes' if briefing else 'no'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
