"""Portal entry page (<output_dir>/index.html): one card per site of config.json."""
import shutil

from common import ASSETS, ROOT, esc, icon_src, related_sites


def _portal_favicon_tag(cfg):
    """Return <link rel="icon"> for the portal index page."""
    icon_cfg = cfg.get("portal_icon")
    src = icon_src(icon_cfg)
    if not src:
        return ""
    if src.endswith(".svg"):
        return f'<link rel="icon" type="image/svg+xml" href="{esc(src)}">'
    return f'<link rel="icon" href="{esc(src)}">'


def _portal_footer_html(updated):
    """Return the portal-level disclaimer and timestamp footer."""
    return (
        f'<footer>'
        f'<p class="footer-disclaimer">'
        f'All sources are publicly available. AI-assisted intelligence compiled for consulting team use only.<br>'
        f'Independent portal — does not represent the official views of the referenced companies.'
        f'</p>'
        f'<p class="footer-updated">Last updated: <time>{updated}</time></p>'
        f'</footer>'
    )


def _portal_header_icon(cfg):
    """Return an <img> or fallback emoji for the main portal header."""
    icon_cfg = cfg.get("portal_icon")
    src = icon_src(icon_cfg)
    if not src:
        emoji = esc(icon_cfg.get("default", "📡")) if isinstance(icon_cfg, dict) else "📡"
        return f'<span style="margin-right:8px;">{emoji}</span>'
    return f'<img src="{esc(src)}" alt="" style="width:28px;height:28px;object-fit:contain;border-radius:6px;vertical-align:middle;margin-right:10px;">'


def render_portal(cfg, output_dir, updated, gc_snippet):
    """Generate the portal entry page listing all sites."""
    portal_name = cfg.get("portal_name", "Industry Watch")
    portal_desc = cfg.get("portal_description", "")
    root_url = cfg["site_root_url"].rstrip("/") + "/"

    p_icon_cfg = cfg.get("portal_icon")
    if isinstance(p_icon_cfg, dict):
        local = p_icon_cfg.get("path", "").strip()
        if local:
            src_icon = ROOT / local
            if src_icon.exists():
                shutil.copy2(src_icon, output_dir / src_icon.name)

    def _resolve_portal_icon(icon_cfg, sid, default_emoji="🌐"):
        if not icon_cfg:
            return esc(default_emoji)
        if isinstance(icon_cfg, str):
            return esc(icon_cfg)
        emoji = esc(icon_cfg.get("default") or default_emoji)
        src = icon_src(icon_cfg)
        if not src:
            return emoji
        if not src.startswith("http://") and not src.startswith("https://"):
            src = f"{sid}/{src}"
        return (
            f'<img src="{esc(src)}" alt="{emoji}" style="width:40px;height:40px;object-fit:contain;border-radius:6px;vertical-align:middle;" '
            f'onerror="this.replaceWith(document.createTextNode(\'{emoji}\'))">'
        )

    sections: dict[str, list] = {}
    for s in cfg["sites"]:
        sec = s.get("section", "Portals")
        sections.setdefault(sec, []).append(s)

    content_sections = ""
    for sec_name, site_list in sections.items():
        cards = ""
        for s in site_list:
            sid = s["id"]
            status = s.get("status", "live")
            icon = _resolve_portal_icon(s.get("site_icon"), sid, "🌐")
            name = esc(s["site_name"])
            desc = esc(s["site_description"])
            url = esc(sid + "/index.html")
            badge = '<span class="portal-badge">🚧 Under construction</span>' if status == "under_construction" else ""
            extra_cls = " portal-card--wip" if status == "under_construction" else ""
            rel = "".join(
                f'<div class="portal-rel"><span>{label}:</span> {esc(", ".join(g["site_name"] for g in group))}</div>'
                for label, group in related_sites(cfg["sites"], s)
            )
            cards += (
                f'<a href="{url}" class="portal-card{extra_cls}">'
                f'<div class="portal-card-header">'
                f'<div class="portal-icon">{icon}</div>'
                f'<div class="portal-name">{name}{badge}</div>'
                f'</div>'
                f'<div class="portal-desc">{desc}</div>'
                f'{rel}'
                f'</a>'
            )
        sec_title = f'<h2 class="portal-section-title">{esc(sec_name)}</h2>' if len(sections) > 1 else ''
        content_sections += f'<section class="portal-section">{sec_title}<div class="portal-grid">{cards}</div></section>'

    portal_css = (ASSETS / "portal.css").read_text(encoding="utf-8")
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(portal_name)}</title>
<meta name="description" content="{esc(portal_desc)}">
{_portal_favicon_tag(cfg)}
<style>{portal_css}</style>
</head>
<body>
<header>
  <h1>{_portal_header_icon(cfg)}{esc(portal_name)}</h1>
  <nav><a href="stats.html" class="stats-btn">📊 Stats</a></nav>
</header>
<div class="portal-wrap">
  <p class="portal-updated">Last updated: <time>{updated}</time></p>
  {content_sections}
</div>
{_portal_footer_html(updated)}
{gc_snippet}
</body>
</html>
"""
    (output_dir / "index.html").write_text(html_out, encoding="utf-8")
    print(f"Portal index.html written ({len(cfg['sites'])} sites)")
