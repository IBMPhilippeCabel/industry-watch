"""Helpers shared by build.py, render.py and its modules (imported as `from common import ...`)."""
import argparse
import html
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "assets"

DEFAULT_CATEGORIES = ["📈 Market", "🤝 M&A", "⚖️ Regulation", "💡 Innovation"]


def parse_args(description, output_dir=False):
    """Command line of build.py / render.py: `--site <id>` is required (no silent default site)."""
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--site", required=True, metavar="ID", help="site id, as in config.json")
    if output_dir:
        p.add_argument("output_dir", help="folder the site is written into")
    return p.parse_args()


def pick_site(cfg, site_id):
    """The site of config.json whose id is `site_id`; exits with the list of valid ids otherwise."""
    for s in cfg["sites"]:
        if s["id"] == site_id:
            return s
    ids = ", ".join(s["id"] for s in cfg["sites"])
    raise SystemExit(f"ERROR: site id {site_id!r} not found in config.json (available: {ids})")

# Typographic apostrophes and accents differ between feeds ("L’Oréal" vs "L'Oreal").
_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u00b4": "'", "`": "'"})


def norm(text):
    """Lowercase, accent-free, straight-apostrophe, single-spaced version of `text`."""
    text = unicodedata.normalize("NFKD", str(text or "").translate(_APOSTROPHES))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).lower().strip()


@lru_cache(maxsize=None)
def _term_re(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(norm(term)) + r"(?![a-z0-9])")


def mentions(norm_text, term):
    """True if `term` appears in `norm_text` (already passed through norm()) as a whole word/phrase."""
    return bool(_term_re(term).search(norm_text))


def site_categories(site_cfg, sources):
    """Topic buttons of a site: `categories` from config.json, else the sources' default_category values."""
    if site_cfg.get("categories"):
        return list(site_cfg["categories"])
    cats = []
    for s in sources:
        c = s.get("default_category")
        if c and c not in cats:
            cats.append(c)
    return cats or list(DEFAULT_CATEGORIES)


def map_category(cat, categories):
    """Return the site category that `cat` belongs to, or None.

    `cat` itself if the site has it; otherwise the site category containing its label,
    e.g. "💡 Innovation" -> "💡 Innovation & RTD", "🤝 M&A" -> "🤝 Strategy & M&A".
    """
    if cat in categories:
        return cat
    label = cat.split(" ", 1)[-1].strip().lower()
    if not label:
        return None
    for c in categories:
        if label in c.lower():
            return c
    return None


# ── HTML / site helpers (render side) ─────────────────────────────────────
def esc(v):
    return html.escape(v or "", quote=True)


def art_day(a):
    return (a.get("date") or "")[:10] or a["first_seen"].isoformat()


def updated_iso(updated):
    return updated.replace(" UTC", "").replace(" ", "T") + ":00Z"


def icon_src(icon_cfg):
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


def industries(site_cfg):
    """Ids of the industry sites a company account belongs to (`industry`: id or list of ids)."""
    ind = site_cfg.get("industry", [])
    return [ind] if isinstance(ind, str) else list(ind)


def related_sites(sites, site_cfg):
    """[(label, [site cfg, ...])] among `sites`: parent industries of an account, or accounts tracked under an industry."""
    parents = [s for s in sites if s["id"] in industries(site_cfg)]
    children = [s for s in sites if site_cfg["id"] in industries(s)]
    return [(label, group) for label, group in (("Industry", parents), ("Accounts", children)) if group]


def safe_url(url):
    """The url if it is an absolute http(s) link without control characters or spaces, else "".

    `esc()` protects attributes from quotes but not from `javascript:` / `data:` schemes: any link
    that comes from a feed must pass through here before it is written into an href.
    """
    url = (url or "").strip()
    if re.search(r"[\x00-\x20\x7f]", url):
        return ""
    parts = urlparse(url)
    return url if parts.scheme in ("http", "https") and parts.netloc else ""


def clean_text(text):
    """Plain text from feed markup: tags and comments removed, entities decoded.

    Markup is removed again after decoding, because a feed may ship its HTML as entities
    (`&lt;script&gt;`), which would otherwise turn into a real tag in the stored text. Only things
    that look like a tag or a comment are removed: a lone `<` or `>` ("margin > 20%") is real text
    and stays (every HTML sink escapes it with esc(), and the JSON-LD writer encodes it).
    """
    markup = re.compile(r"<!--.*?(?:-->|$)|</?[A-Za-z!?][^>]*>", re.S)
    text = markup.sub(" ", text or "")
    text = markup.sub(" ", html.unescape(text))
    return re.sub(r"\s+", " ", text).strip()
