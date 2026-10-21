"""Helpers shared by build.py and render.py (imported as `from common import ...`)."""
import re
import unicodedata
from functools import lru_cache

DEFAULT_CATEGORIES = ["📈 Market", "🤝 M&A", "⚖️ Regulation", "💡 Innovation"]

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
