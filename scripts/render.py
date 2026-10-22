#!/usr/bin/env python3
"""Render the static site from data/YYYY/MM/DD.json and DD.briefing.txt.

Usage: python scripts/render.py --site <id> <output_dir>

For a given site id, writes into <output_dir>/<id>/:
  index.html              articles of the last ROLLING_DAYS days
  archive/YYYY-MM.html    all articles for that month
  archive/index.html      list of monthly archive pages

Also writes <output_dir>/index.html  (portal entry page listing all sites).
"""
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cards import briefing_block, cards_section
from common import ASSETS, ROOT, parse_args, pick_site, related_sites, site_categories, updated_iso
from layout import (SiteCtx, archive_dropdown_html, page_jsonld, render_under_construction,
                    shell, site_relations_html, sources_dropdown_html)
from loader import load_all
from machine_files import write_machine_files
from portal import render_portal

ARGS = parse_args("Render the static pages of one site.", output_dir=True)
GLOBAL_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
CFG = pick_site(GLOBAL_CFG, ARGS.site)

GOATCOUNTER_URL = GLOBAL_CFG.get("goatcounter_url", "")
SOURCES = json.loads((ROOT / CFG["sources_file"]).read_text(encoding="utf-8"))

CTX = SiteCtx(
    cfg=CFG,
    global_cfg=GLOBAL_CFG,
    sources=SOURCES,
    categories=site_categories(CFG, SOURCES),
    name=CFG["site_name"],
    desc=CFG["site_description"],
    url=GLOBAL_CFG["site_root_url"].rstrip("/") + "/" + CFG["id"] + "/",
    rolling_days=int(CFG.get("rolling_days", 30)),
    gc_snippet=(
        f'<script data-goatcounter="{GOATCOUNTER_URL}" async src="//gc.zgo.at/count.js"></script>'
        if GOATCOUNTER_URL else ""
    ),
    css=(ASSETS / "site.css").read_text(encoding="utf-8"),
    filter_js=(ASSETS / "filter.js").read_text(encoding="utf-8"),
)


def main():
    output_dir = Path(ARGS.output_dir).resolve()

    # Site output goes into output_dir/<id>/
    site = output_dir / CFG["id"]
    site.mkdir(parents=True, exist_ok=True)

    # Copy local icon into site dir so relative src works after deploy.
    icon_cfg = CFG.get("site_icon")
    if isinstance(icon_cfg, dict):
        local = icon_cfg.get("path", "").strip()
        if local:
            src_icon = ROOT / local
            if src_icon.exists():
                shutil.copy2(src_icon, site / src_icon.name)

    now = datetime.now(timezone.utc)
    updated = f"{now:%Y-%m-%d %H:%M UTC}"

    # If under construction: write placeholder page and skip full render.
    if CFG.get("status") == "under_construction":
        render_under_construction(CTX, site, updated)
        render_portal(GLOBAL_CFG, output_dir, updated, CTX.gc_snippet)
        return 0

    articles, briefing = load_all(ROOT / CFG["data_dir"])
    if not articles:
        print(f"[{CFG['id']}] No articles yet — rendering waiting state until first sync")
        render_under_construction(CTX, site, updated)
        render_portal(GLOBAL_CFG, output_dir, updated, CTX.gc_snippet)
        return 0

    cutoff = now.date() - timedelta(days=CTX.rolling_days)

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
    body = (updated_line + site_relations_html(related_sites(GLOBAL_CFG["sites"], CFG))
            + briefing_block(CTX, briefing) + cards_section(CTX, recent))
    home_desc = (briefing[1].get("hook") if briefing else "") or CTX.desc
    (site / "index.html").write_text(
        shell(CTX, f"{CTX.name} — news", body, updated,
              CTX.filter_js, path=f"{CFG['id']}/", description=home_desc,
              jsonld=page_jsonld(CTX, CTX.name, f"{CFG['id']}/", home_desc, recent),
              sources_html=sources_dropdown_html(CTX),
              archive_html=archive_dropdown_html(all_months_keys, months)),
        encoding="utf-8",
    )

    # ── <id>/archive/YYYY-MM.html ─────────────────────────────────────
    for ym, items in months.items():
        body = updated_line + cards_section(CTX, items)
        desc = f"{CTX.name} archive {ym}: {len(items)} articles."
        (archive / f"{ym}.html").write_text(
            shell(CTX, f"{CTX.name} — Archive {ym}", body, updated, CTX.filter_js,
                  path=f"{CFG['id']}/archive/{ym}.html", description=desc,
                  jsonld=page_jsonld(CTX, f"{CTX.name} archive {ym}", f"{CFG['id']}/archive/{ym}.html", desc, items),
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
    (archive / "index.html").write_text(
        shell(CTX, f"{CTX.name} — Archive", f'<ul class="months">{rows}</ul>', updated,
              path=f"{CFG['id']}/archive/index.html",
              description=f"Monthly archive of {CTX.name} articles.",
              archive_html=archive_dropdown_html(all_months_keys, months),
              depth=2),
        encoding="utf-8",
    )

    write_machine_files(site, articles, recent, briefing, now, site_url=CTX.url, site_name=CTX.name,
                        site_desc=CTX.desc, rolling_days=CTX.rolling_days, categories=CTX.categories,
                        sources=CTX.sources)

    # ── portal index.html (always regenerated, lists all sites) ──────
    render_portal(GLOBAL_CFG, output_dir, updated, CTX.gc_snippet)

    print(
        f"[{CFG['id']}] index.html: {len(recent)} articles (last {CTX.rolling_days} days); "
        f"{len(months)} monthly archive page(s); briefing={'yes' if briefing else 'no'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
