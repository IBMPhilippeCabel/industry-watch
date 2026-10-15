#!/usr/bin/env python3
"""Generate stats pages from GoatCounter API data.

Usage: python scripts/stats.py <output_dir>

Reads GOATCOUNTER_API_KEY from environment.
Reads goatcounter_url and sites from config.json.

Writes:
  <output_dir>/stats.html              — global stats (all sites)
  <output_dir>/<site_id>/stats.html    — per-site stats
"""
import html
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def esc(v):
    return html.escape(str(v) if v else "", quote=True)


def _load_config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def _api_get(base_url, path, token):
    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def _fetch_stats(api_base, token):
    """Fetch hits (all pages), countries, and browsers from GoatCounter API."""
    hits, countries, browsers = [], [], []
    try:
        data = _api_get(api_base, "/api/v0/stats/hits?limit=100", token)
        hits = data.get("hits", [])
    except Exception as e:
        print(f"WARN: could not fetch hits: {e}", file=sys.stderr)
    try:
        data = _api_get(api_base, "/api/v0/stats/countries?limit=30", token)
        countries = data.get("countries", [])
    except Exception as e:
        print(f"WARN: could not fetch countries: {e}", file=sys.stderr)
    try:
        data = _api_get(api_base, "/api/v0/stats/browsers?limit=10", token)
        browsers = data.get("browsers", [])
    except Exception as e:
        print(f"WARN: could not fetch browsers: {e}", file=sys.stderr)
    return hits, countries, browsers


def _group_hits_by_site(hits, sites, site_root_path):
    """Return dict: site_id → list of hit dicts. Unmatched hits go to '_portal'."""
    groups = {s["id"]: [] for s in sites}
    groups["_portal"] = []
    root = site_root_path.rstrip("/") + "/"
    for h in hits:
        path = h.get("path", "")
        matched = False
        for s in sites:
            prefix = root + s["id"] + "/"
            if path.startswith(prefix) or path == root + s["id"]:
                groups[s["id"]].append(h)
                matched = True
                break
        if not matched:
            groups["_portal"].append(h)
    return groups


def _total(items):
    return sum(i.get("count", 0) for i in items)


COUNTRY_FLAGS = {
    "US": "🇺🇸", "FR": "🇫🇷", "GB": "🇬🇧", "DE": "🇩🇪", "NL": "🇳🇱",
    "BE": "🇧🇪", "CH": "🇨🇭", "CA": "🇨🇦", "AU": "🇦🇺", "JP": "🇯🇵",
    "CN": "🇨🇳", "IN": "🇮🇳", "BR": "🇧🇷", "MX": "🇲🇽", "IT": "🇮🇹",
    "ES": "🇪🇸", "PT": "🇵🇹", "PL": "🇵🇱", "SE": "🇸🇪", "NO": "🇳🇴",
    "DK": "🇩🇰", "FI": "🇫🇮", "SG": "🇸🇬", "HK": "🇭🇰", "NZ": "🇳🇿",
    "(unknown)": "🌐",
}


def _flag(code):
    return COUNTRY_FLAGS.get(code, "🌐")


def _bar(count, max_count, color="var(--accent)"):
    pct = int(count / max_count * 100) if max_count else 0
    return (
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<div style="flex:1;background:var(--border);border-radius:4px;height:8px;">'
        f'<div style="width:{pct}%;background:{color};height:8px;border-radius:4px;"></div>'
        f'</div>'
        f'<span style="min-width:40px;text-align:right;font-size:13px;color:var(--muted);">{count:,}</span>'
        f'</div>'
    )


def _pages_table(hits, color="var(--accent)", limit=10):
    if not hits:
        return '<p class="muted">No data yet.</p>'
    max_h = hits[0]["count"]
    rows = "".join(
        f'<tr>'
        f'<td style="font-size:12px;word-break:break-all;color:var(--muted);">{esc(h.get("path",""))}</td>'
        f'<td style="width:55%;padding-left:10px;">{_bar(h["count"], max_h, color)}</td>'
        f'</tr>'
        for h in hits[:limit]
    )
    return (
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>'
        f'<th style="text-align:left;font-size:11px;color:var(--muted);padding-bottom:6px;">Page</th>'
        f'<th style="text-align:left;font-size:11px;color:var(--muted);padding-bottom:6px;padding-left:10px;">Views</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
    )


def _country_table(countries):
    active = [c for c in countries if c.get("count", 0) > 0]
    if not active:
        return '<p class="muted">No data yet.</p>'
    max_c = active[0]["count"]
    rows = "".join(
        f'<tr>'
        f'<td style="font-size:13px;white-space:nowrap;">{_flag(c.get("country",""))} {esc(c.get("country_name") or c.get("country",""))}</td>'
        f'<td style="width:60%;padding-left:12px;">{_bar(c["count"], max_c, "var(--ai)")}</td>'
        f'</tr>'
        for c in active
    )
    return (
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>'
        f'<th style="text-align:left;font-size:12px;color:var(--muted);padding-bottom:8px;">Country</th>'
        f'<th style="text-align:left;font-size:12px;color:var(--muted);padding-bottom:8px;padding-left:12px;">Views</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
    )


def _browser_table(browsers):
    active = [b for b in browsers if b.get("count", 0) > 0]
    if not active:
        return '<p class="muted">No data yet.</p>'
    max_b = active[0]["count"]
    rows = "".join(
        f'<tr>'
        f'<td style="font-size:13px;">{esc(b.get("browser",""))}</td>'
        f'<td style="width:60%;padding-left:12px;">{_bar(b["count"], max_b, "#10b981")}</td>'
        f'</tr>'
        for b in active
    )
    return (
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>'
        f'<th style="text-align:left;font-size:12px;color:var(--muted);padding-bottom:8px;">Browser</th>'
        f'<th style="text-align:left;font-size:12px;color:var(--muted);padding-bottom:8px;padding-left:12px;">Views</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
    )


_STATS_CSS = """
  :root { --bg:#f7f8fa; --card:#fff; --border:#e5e7eb; --text:#1f2328; --muted:#57606a; --accent:#3b82d4; --ai:#7c5cd8; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.6 -apple-system,"Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }
  header { background:var(--card); border-bottom:1px solid var(--border); padding:14px 24px; display:flex; justify-content:space-between; align-items:center; }
  header h1 { margin:0; font-size:20px; }
  header nav a { color:var(--accent); text-decoration:none; font-size:14px; margin-left:20px; }
  .wrap { max-width:1100px; margin:0 auto; padding:24px; }
  .kpi-row { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:16px; margin-bottom:24px; }
  .kpi { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px 20px; }
  .kpi-value { font-size:28px; font-weight:700; }
  .kpi-label { font-size:12px; color:var(--muted); margin-top:2px; }
  .section-title { font-size:13px; font-weight:600; margin:28px 0 10px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; border-bottom:1px solid var(--border); padding-bottom:6px; }
  .sites-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(460px,1fr)); gap:16px; margin-bottom:28px; }
  .site-section { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:20px; }
  .site-section-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }
  .site-section h2 { margin:0; font-size:15px; }
  .kpi-inline { font-size:13px; font-weight:600; color:var(--accent); }
  .two-col { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  @media(max-width:700px) { .two-col, .sites-grid { grid-template-columns:1fr; } }
  .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:20px; }
  .card h2 { margin:0 0 16px; font-size:15px; }
  tr { border-bottom:1px solid var(--border); }
  td { padding:6px 0; vertical-align:middle; }
  .muted { color:var(--muted); font-size:13px; }
  footer { text-align:center; color:var(--muted); font-size:12px; padding:16px; border-top:1px solid var(--border); margin-top:24px; }
"""


def render_global_stats(hits, countries, browsers, cfg, gc_dashboard_url, updated):
    """Global stats page for the portal (stats.html at root)."""
    sites = cfg["sites"]
    portal_name = cfg.get("portal_name", "Industry Watch")
    site_root_path = urlparse(cfg["site_root_url"].rstrip("/") + "/").path

    total_views = _total(hits)
    total_countries = len([c for c in countries if c.get("count", 0) > 0])
    groups = _group_hits_by_site(hits, sites, site_root_path)

    # Per-site summary blocks
    site_sections = ""
    for s in sites:
        sid = s["id"]
        name = esc(s["site_name"])
        site_hits = groups[sid]
        total = _total(site_hits)
        site_sections += (
            f'<div class="site-section">'
            f'<div class="site-section-header">'
            f'<h2><a href="{esc(sid)}/stats.html" style="color:var(--text);text-decoration:none;">{name}</a></h2>'
            f'<span class="kpi-inline">{total:,} views</span>'
            f'</div>'
            f'{_pages_table(site_hits)}'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(portal_name)} — Stats</title>
<style>{_STATS_CSS}</style>
</head>
<body>
<header>
  <h1>📊 {esc(portal_name)} — Stats</h1>
  <nav><a href="index.html">🏠 Portal</a></nav>
</header>
<main class="wrap">
  <div class="kpi-row">
    <div class="kpi"><div class="kpi-value">{total_views:,}</div><div class="kpi-label">Total page views</div></div>
    <div class="kpi"><div class="kpi-value">{total_countries}</div><div class="kpi-label">Countries</div></div>
    <div class="kpi"><div class="kpi-value">{len(sites)}</div><div class="kpi-label">Sites tracked</div></div>
  </div>

  <div class="section-title">By site</div>
  <div class="sites-grid">{site_sections}</div>

  <div class="section-title">Global breakdown</div>
  <div class="two-col">
    <div class="card"><h2>🌍 Countries</h2>{_country_table(countries)}</div>
    <div class="card">
      <h2>🖥️ Browsers</h2>{_browser_table(browsers)}
      <div style="margin-top:20px;text-align:center;">
        <a href="{esc(gc_dashboard_url)}" target="_blank" rel="noopener"
           style="background:var(--accent);color:#fff;border-radius:8px;padding:8px 18px;text-decoration:none;font-size:13px;font-weight:600;">
          Full GoatCounter dashboard →
        </a>
      </div>
    </div>
  </div>
  <p class="muted" style="margin-top:12px;">Last updated: {updated}</p>
</main>
<footer>Powered by <a href="https://www.goatcounter.com" target="_blank" rel="noopener">GoatCounter</a></footer>
</body>
</html>
"""


def render_site_stats(site_cfg, site_hits, countries, browsers, portal_name, gc_dashboard_url, updated):
    """Per-site stats page written into <site_id>/stats.html."""
    name = esc(site_cfg["site_name"])
    total_views = _total(site_hits)
    total_pages = len(site_hits)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — Stats</title>
<style>{_STATS_CSS}</style>
</head>
<body>
<header>
  <h1>📊 {name} — Stats</h1>
  <nav>
    <a href="index.html">← {name}</a>
    <a href="../stats.html">🌐 Global stats</a>
    <a href="../index.html">🏠 Portal</a>
  </nav>
</header>
<main class="wrap">
  <div class="kpi-row">
    <div class="kpi"><div class="kpi-value">{total_views:,}</div><div class="kpi-label">Page views</div></div>
    <div class="kpi"><div class="kpi-value">{total_pages}</div><div class="kpi-label">Tracked pages</div></div>
  </div>

  <div class="section-title">Top pages</div>
  <div class="card" style="margin-bottom:24px;">{_pages_table(site_hits, limit=20)}</div>

  <div class="section-title">Global breakdown (all sites)</div>
  <div class="two-col">
    <div class="card"><h2>🌍 Countries</h2>{_country_table(countries)}</div>
    <div class="card">
      <h2>🖥️ Browsers</h2>{_browser_table(browsers)}
      <div style="margin-top:20px;text-align:center;">
        <a href="{esc(gc_dashboard_url)}" target="_blank" rel="noopener"
           style="background:var(--accent);color:#fff;border-radius:8px;padding:8px 18px;text-decoration:none;font-size:13px;font-weight:600;">
          Full GoatCounter dashboard →
        </a>
      </div>
    </div>
  </div>
  <p class="muted" style="margin-top:12px;">Last updated: {updated}</p>
</main>
<footer>Powered by <a href="https://www.goatcounter.com" target="_blank" rel="noopener">GoatCounter</a></footer>
</body>
</html>
"""


def main():
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print("Usage: stats.py <output_dir>", file=sys.stderr)
        return 2

    token = os.environ.get("GOATCOUNTER_API_KEY", "")
    if not token:
        print("ERROR: GOATCOUNTER_API_KEY not set", file=sys.stderr)
        return 1

    cfg = _load_config()
    gc_url = cfg.get("goatcounter_url", "")
    if not gc_url:
        print("ERROR: goatcounter_url not set in config.json", file=sys.stderr)
        return 1

    api_base = gc_url.rstrip("/").removesuffix("/count")
    gc_dashboard_url = api_base
    portal_name = cfg.get("portal_name", "Industry Watch")
    site_root_path = urlparse(cfg["site_root_url"].rstrip("/") + "/").path

    output_dir = Path(args[0]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    updated = f"{now:%Y-%m-%d %H:%M UTC}"

    hits, countries, browsers = _fetch_stats(api_base, token)
    groups = _group_hits_by_site(hits, cfg["sites"], site_root_path)

    # Global stats at root
    (output_dir / "stats.html").write_text(
        render_global_stats(hits, countries, browsers, cfg, gc_dashboard_url, updated),
        encoding="utf-8",
    )

    # Per-site stats
    for s in cfg["sites"]:
        site_dir = output_dir / s["id"]
        site_dir.mkdir(parents=True, exist_ok=True)
        (site_dir / "stats.html").write_text(
            render_site_stats(s, groups[s["id"]], countries, browsers, portal_name, gc_dashboard_url, updated),
            encoding="utf-8",
        )

    print(f"stats.html written — global + {len(cfg['sites'])} site pages ({len(hits)} pages, {len(countries)} countries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
