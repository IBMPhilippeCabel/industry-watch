"""Article cards, topic/brand filters and the daily briefing block."""
import hashlib
import re

from common import art_day, esc, map_category, mentions, norm, safe_url


def art_id(a):
    return "a-" + hashlib.sha1(a["link"].encode("utf-8")).hexdigest()[:10]


def briefing_block(ctx, briefing):
    if not briefing:
        return ""
    day, data = briefing
    hook = data.get("hook", "")
    # Older briefings use the generic keys ("💡 Innovation"): file them under the site's own category.
    cats = {}
    for k, v in data.get("categories", {}).items():
        target = map_category(k, ctx.categories)
        if v and target and target not in cats:
            cats[target] = v
    # hook line
    parts = [f'<p class="briefing-hook">{esc(hook)}</p>'] if hook else []
    # one line per category that has content
    for cat in ctx.categories:
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


def tracked_brands(site_cfg):
    """Return dict of brand_term -> (slug, display_name) for the site."""
    acc_filters = site_cfg.get("account_filters", {})
    brands_cfg = site_cfg.get("brands", [])
    candidates = []
    if isinstance(acc_filters, dict):
        candidates.extend(acc_filters.get("owned_brands", []))
        candidates.extend(acc_filters.get("in_acquisition", []))
    if isinstance(brands_cfg, list):
        candidates.extend(brands_cfg)

    tracked = {}
    seen_slugs = set()
    for b in candidates:
        b_clean = b.strip()
        if not b_clean:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", norm(b_clean)).strip("-")
        if slug in seen_slugs:      # same brand spelled twice (accent / apostrophe variants)
            continue
        seen_slugs.add(slug)
        name = " ".join(w[:1].upper() + w[1:] for w in b_clean.split())
        name = name.replace("M&m's", "M&M's").replace("M&ms", "M&M's")
        name = name.replace("Rtd", "RTD").replace("Esg", "ESG")
        tracked[b_clean.lower()] = (slug, name)
    return tracked


def cards_section(ctx, articles):
    cat_buttons = ['<button class="active" data-cat="all">All</button>'] + [
        f'<button data-cat="{esc(c)}">{esc(c)}</button>' for c in ctx.categories
    ]

    brands = tracked_brands(ctx.cfg)
    active_brands = {}

    rows = []
    for a in articles:
        d = art_day(a)
        ai = a.get("ai_summary", "")
        ai_html = f'<div class="ai-summary"><span class="ai-icon">🤖</span> {esc(ai)}</div>' if ai else ""

        full_text = norm(f"{a.get('title', '')} {a.get('summary', '')}")
        matched_slugs = set()
        matched_names = set()
        for b_term, (slug, b_name) in brands.items():
            if mentions(full_text, b_term):
                matched_slugs.add(slug)
                matched_names.add(b_name)
                active_brands[slug] = b_name

        brands_attr = ",".join(sorted(matched_slugs))
        brand_tags = "".join(f'<span class="brand-tag">{esc(bn)}</span>' for bn in sorted(matched_names)[:2])

        # Stored categories may predate the site's category list: show them under the matching button.
        cat = map_category(a["category"], ctx.categories) or a["category"]
        link = safe_url(a["link"])
        title_html = (
            f'<a href="{esc(link)}" target="_blank" rel="noopener">{esc(a["title"])}</a>' if link else esc(a["title"])
        )
        rows.append(
            f'<article class="card" id="{art_id(a)}" data-cat="{esc(cat)}" data-brands="{esc(brands_attr)}">'
            f'<div class="meta"><span class="tag">{esc(cat)}</span>'
            f'{brand_tags}'
            f'<span>{esc(a["source"])}</span><time datetime="{d}">{d}</time></div>'
            f'{ai_html}'
            f'<h2>{title_html}</h2>'
            f'<p>{esc(a["summary"])}</p></article>'
        )

    brand_nav = ""
    if len(active_brands) >= 2:
        sorted_b = sorted(active_brands.items(), key=lambda x: x[1])
        b_buttons = ['<button class="active" data-brand="all">All</button>'] + [
            f'<button data-brand="{esc(slug)}">{esc(name)}</button>' for slug, name in sorted_b
        ]
        brand_nav = f'<nav class="filters brand-filters"><span class="filters-label">🏷️ Brands:</span>{"".join(b_buttons)}</nav>'

    cat_nav = f'<nav class="filters cat-filters"><span class="filters-label">Topics:</span>{"".join(cat_buttons)}</nav>'
    grid = "".join(rows) or '<p class="muted">No articles.</p>'
    return f'{cat_nav}{brand_nav}<div class="grid">{grid}</div>'
